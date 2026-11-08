from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

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
        assert stable.json()["lineages"][0]["metadata"]["manifest_hash"] == (first.manifest_hash)
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


def test_model_input_result_owned_path_binds_control_alias_core_run_and_exact_job(
    runtime_api_env,
    monkeypatch,
) -> None:
    """Resolve the Control alias and action job before OPA without losing either selector."""
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from fastapi import Depends
    from fastapi.routing import APIRoute

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http import resource_binding
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobExecutionScope,
        ControlJobRecord,
    )
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _action_permission_dependencies,
        _claims,
        _fixture_bearer,
    )

    opa = _CaptureOPA()
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    core_run_id = "core-ds20-model-input-owned-path"
    control_run_id = "R_ds20_model_input_control_alias"
    control_owner_job_id = "job-ds20-model-input-control-owner"
    action_job_id = "job-ds20-model-input-action"
    tenant_id = str(runtime_api_env["tenant_a"])
    cell_id = cell.cell_id

    store = FileSystemCAS(runtime_api_env["cas_root"])
    registry_ref = store.put_json(
        {"registry": {}, "purpose": "model-input-result-owned-path"},
        ArtifactWriteOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    core = RunContext.start(
        store=store,
        registry_bundle=registry_ref,
        run_id=core_run_id,
        run_dir=runtime_api_env["cas_root"] / "runs" / core_run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    core.run_manifest.control_job_id = control_owner_job_id
    core.finalize()
    context = client.app.state.runtime_container.runtime_api_context
    context.run_index.refresh(force=True)
    indexed = context.run_index.get_run(core_run_id)
    assert indexed.details.manifest_ref is not None
    owner_binding = resource_binding._OwnedRunBinding(
        control_run_id=control_run_id,
        core_run_id=core_run_id,
        control_job_id=control_owner_job_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        core_manifest_ref=indexed.details.manifest_ref.model_dump(mode="json"),
    )

    def resolve_control_alias(request, ctx, scope, *, control_run_id: str):
        del request
        assert ctx is context
        assert control_run_id == control_run_id_for_test
        return control_run_id, tenant_id, owner_binding

    control_run_id_for_test = control_run_id
    monkeypatch.setattr(
        resource_binding,
        "_resolve_completed_nl_control_alias",
        resolve_control_alias,
    )

    now = datetime.now(UTC)

    def action_job(*, run_id: str = control_run_id, kind: str = "acquisition"):
        return ControlJobRecord(
            job_id=action_job_id,
            kind=kind,
            state="completed",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile=None,
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref="sha256:" + "a" * 64,
            submitted_by="test-operator",
            created_at=now,
            started_at=now,
            finished_at=now,
            lease_owner=None,
            lease_expires_at=None,
            attempt=1,
            error_message=None,
            progress={},
        )

    owner_scope = ControlJobExecutionScope(
        status="established",
        tenant_id=tenant_id,
        cell_id=cell_id,
        actor_subject="test-operator",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    mutable = {"job": action_job(), "scope": owner_scope}
    control_store = SimpleNamespace(
        get_job=lambda job_id: mutable["job"],
        _reconcile_control_job_creation_envelope=lambda _job: (mutable["scope"], None),
    )
    monkeypatch.setattr(
        resource_binding,
        "resolve_control_service",
        lambda _request: SimpleNamespace(_control_store=control_store),
    )

    bearer = _fixture_bearer("model-input-owned-path")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant_id,
            cell_id=cell_id,
            jti="jwt-model-input-owned-path",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant_id}

    route = next(
        item
        for item in client.app.routes
        if isinstance(item, APIRoute)
        and item.path == "/api/v1/runs/{run_id}/model-input-use/{job_id}/n5-result"
        and "GET" in (item.methods or set())
    )
    (dependency,) = _action_permission_dependencies(route)

    @client.app.get(
        "/api/v1/ds20/model-input-use-owned-path/{run_id}/{job_id}",
        dependencies=[Depends(dependency)],
    )
    def owned_path_probe(run_id: str, job_id: str, request: Request) -> dict[str, object]:
        bound_resource = request.state.authz_bound_resource
        return {
            "run_id": run_id,
            "job_id": job_id,
            "resource_id": bound_resource.resource_id,
            "selectors": dict(bound_resource.canonical_selectors),
        }

    path = f"/api/v1/ds20/model-input-use-owned-path/{control_run_id}/{action_job_id}"
    owned = client.get(path, headers=headers)
    assert owned.status_code == 200, owned.text
    assert owned.json() == {
        "run_id": control_run_id,
        "job_id": action_job_id,
        "resource_id": opa.inputs[0].resource_artifact_id,
        "selectors": {
            "cell_id": f'"{cell_id}"',
            "core_run_id": f'"{core_run_id}"',
            "job_id": f'"{action_job_id}"',
            "run_id": f'"{control_run_id}"',
        },
    }
    assert len(opa.inputs) == 1
    bound = opa.inputs[0]
    assert bound.action_permission is RuntimePermission.RUNS_REVIEW
    assert bound.action_resource_class == "runtime.run.model_input_use_result"
    assert bound.resource_tenant_id == tenant_id
    assert bound.resource_kind == "runtime.run.model_input_use_result.ownership_verified"
    assert bound.resource_artifact_id == owned.json()["resource_id"]

    mutable["job"] = action_job(run_id="R_foreign_control_alias")
    wrong_run = client.get(path, headers=headers)
    assert wrong_run.status_code == 403
    assert wrong_run.json()["code"] == "authorization_binding_job_unresolved"
    assert len(opa.inputs) == 1

    mutable["job"] = action_job(kind="workflow_run")
    wrong_kind = client.get(path, headers=headers)
    assert wrong_kind.status_code == 403
    assert wrong_kind.json()["code"] == "authorization_binding_job_unresolved"
    assert len(opa.inputs) == 1

    mutable["job"] = action_job()
    mutable["scope"] = owner_scope.__class__(
        status="established",
        tenant_id="tenant-foreign",
        cell_id=cell_id,
        actor_subject="test-operator",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    wrong_tenant_owner = client.get(path, headers=headers)
    assert wrong_tenant_owner.status_code == 403
    assert wrong_tenant_owner.json()["code"] == "authorization_binding_job_scope_mismatch"
    assert len(opa.inputs) == 1

    mutable["scope"] = owner_scope.__class__(
        status="established",
        tenant_id=tenant_id,
        cell_id="cell-foreign",
        actor_subject="test-operator",
        actor_authenticated=True,
        actor_roles=("analyst",),
    )
    wrong_cell_owner = client.get(path, headers=headers)
    assert wrong_cell_owner.status_code == 403
    assert wrong_cell_owner.json()["code"] == "authorization_binding_job_scope_mismatch"
    assert len(opa.inputs) == 1

    tenant_b_bearer = _fixture_bearer("model-input-owned-path-cross-tenant")
    provider.put_claim(
        tenant_b_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell_id,
            jti="jwt-model-input-owned-path-cross-tenant",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    cross_tenant = client.get(
        path,
        headers={
            "Authorization": f"Bearer {tenant_b_bearer}",
            "X-Tenant-ID": runtime_api_env["tenant_b"],
        },
    )
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["code"] == "authorization_binding_run_unresolved"
    assert len(opa.inputs) == 1


def test_auth_me_openapi_permission_example_equals_canonical_analyst_grants() -> None:
    openapi = create_runtime_api_app().openapi()
    example = openapi["paths"]["/api/v1/auth/me"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["examples"]["default"]["value"]

    assert example["permissions"] == [
        permission.value for permission in permissions_for_roles([PolicyOSRole.ANALYST])
    ]
