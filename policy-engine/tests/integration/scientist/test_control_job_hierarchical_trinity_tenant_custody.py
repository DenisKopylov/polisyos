"""Exercise durable ControlJob tenant scope through the secured launch route."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest


@pytest.fixture
def runtime_api_env(tmp_path: Path, pytestconfig: pytest.Config) -> Iterator[dict[str, object]]:
    """Build and close the shared runtime fixture for this integration module."""
    from _helpers import runtime_http

    if runtime_http.TestClient is None:
        pytest.skip("fastapi is not installed")

    project_root = Path(pytestconfig.rootpath).resolve(strict=True)
    env = runtime_http.build_runtime_api_env(
        tmp_path,
        include_test_client=False,
        app_kwargs={"repo_root": project_root},
    )
    try:
        yield env
    finally:
        runtime_http.close_runtime_api_env(env)


@pytest.mark.integration
def test_admitted_control_job_scope_reaches_hierarchical_trinity_consumer(
    runtime_api_env: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind the worker's durable scope across HTTP launch, Trinity persistence, and reads."""
    from polisyos.core.artifacts import (
        FileSystemCAS,
        PutOptions,
        artifact_manifest_profile_sha256,
        ensure_ir_artifact_store,
        input_ref_from_artifact_ref,
        with_ambient_ownership_enforcement_if_supported,
    )
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo, SchemaInfo
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.control import WorkflowRunRequest
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.core.security.tenant_context import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        tenant_scope,
    )
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import (
        ObjectiveSpec,
        ProblemDomain,
        ProblemFrame,
    )
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.kernel.values import MoneyValue
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.trinity.loaders import (
        TrinityLoadError,
        load_trinity_bundle_artifact,
        persist_trinity_bundle_artifact,
    )
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        _persist_trinity_bundle,
    )
    from polisyos.scientist.orchestration.engine.retry import _node_facing_context
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.workflows import builder
    from tests._helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _build_secure_client,
        _CaptureOPA,
        _claims,
        _fixture_bearer,
    )

    tenant_id = str(runtime_api_env["tenant_a"])
    other_tenant_id = str(runtime_api_env["tenant_b"])
    opa = _CaptureOPA()
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=opa,
        claims_by_token={},
        raise_server_exceptions=False,
    )
    cell_id = cell.cell_id
    bearer = _fixture_bearer("control-job-hierarchical-trinity")
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant_id,
            cell_id=cell_id,
            jti="jwt-control-job-hierarchical-trinity",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": tenant_id,
    }
    observed: dict[str, object] = {}

    def make_bundle() -> TrinityBundle:
        return TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="control_job_trinity_problem",
                domain=ProblemDomain.FISCAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="employment_goal",
                        metric_id="employment_rate",
                        direction=OptimizationDirection.MAXIMIZE,
                    )
                ],
            ),
            policy_spec=PolicySpec(
                policy_id="control_job_trinity_policy",
                interventions=[
                    InterventionSpec(
                        intervention_id="wage_support",
                        kind="wage_subsidy",
                        target=SelectorPredicate(
                            field="region_code",
                            operator=SelectorOperator.EQUALS,
                            value="UA-30",
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=2),
                        params={"amount": MoneyValue(amount=Decimal("10"), currency="UAH")},
                    )
                ],
            ),
            model_spec=ModelSpec(
                model_id="control_job_trinity_model",
                data_snapshot_ref="sha256:" + "2" * 64,
            ),
        )

    def scoped_scientist_execution(
        state_payload: object,
        *,
        store: object,
        **kwargs: object,
    ) -> dict[str, object]:
        del kwargs
        state = ExperimentState.model_validate(state_payload)
        assert state.control_job_id == observed["job_id"]
        assert get_current_access_scope_or_none() is None
        assert get_current_tenant_id_or_none() == tenant_id
        assert get_current_cell_id() == cell_id

        workflow_store = builder._resolve_store(store)
        registry_ref = workflow_store.put_json(
            {"registry": {}},
            PutOptions(
                kind="core.registry.bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.test.CoreRegistryBundle", version="1.0"),
            ),
            return_selected_profile=True,
        )
        context = builder.build_execution_context(
            workflow_store,
            registry_ref,
            run_id=state.run_id,
        )
        completed = False
        try:
            builder._propagate_runtime_run_metadata(context, state)
            assert context.run.access_scope is None
            assert context.run.run_manifest.control_job_id == state.control_job_id
            assert (context.run.tenant_id, context.run.cell_id) == (tenant_id, cell_id)

            node_context = _node_facing_context(context)
            bundle = make_bundle()
            inputs = [
                input_ref_from_artifact_ref(ref, role=key) for key, ref in state.inputs.items()
            ]
            ir_store = ensure_ir_artifact_store(context.store)
            unscoped_sibling = persist_trinity_bundle_artifact(
                ir_store,
                bundle,
                inputs=inputs,
            )
            selected_ref = _persist_trinity_bundle(node_context, bundle, state=state)
            # Core and IR use distinct ArtifactID models; compare their canonical CAS ABI.
            assert str(selected_ref.artifact_id) == str(unscoped_sibling.artifact_id)
            assert selected_ref.manifest_profile_sha256 is not None
            assert selected_ref.manifest_profile_sha256 != unscoped_sibling.manifest_profile_sha256

            tenant_store = FileSystemCAS(context.store.root)
            tenant_reader = tenant_store.for_tenant(tenant_id, cell_id)
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                manifest = tenant_reader.get_manifest(selected_ref)
                assert manifest.tenant_context == ArtifactTenantContextInfo(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                assert (
                    artifact_manifest_profile_sha256(manifest)
                    == selected_ref.manifest_profile_sha256
                )
                loaded_bundle = load_trinity_bundle_artifact(tenant_reader, selected_ref)
                # ParamValue is opaque; compare the persisted JSON representation.
                assert loaded_bundle.model_dump(mode="json") == bundle.model_dump(mode="json")

            foreign_reader = tenant_store.for_tenant(other_tenant_id, cell_id)
            with (
                tenant_scope(None, tenant_id=other_tenant_id, cell_id=cell_id),
                pytest.raises(TrinityLoadError) as refused,
            ):
                load_trinity_bundle_artifact(foreign_reader, selected_ref)
            chain: list[BaseException] = []
            error: BaseException | None = refused.value
            while error is not None:
                chain.append(error)
                error = error.__cause__
            assert any(isinstance(item, ArtifactOwnershipError) for item in chain)

            context.run.add_output(selected_ref)
            observed.update(
                selected_ref=selected_ref,
                tenant_context=manifest.tenant_context,
                loaded_bundle=bundle,
            )
            completed = True
        finally:
            context.run.finalize(status="ok" if completed else "failed")
        return {"run_id": state.run_id, "artifacts_index": {}}

    cas_root = runtime_api_env["cas_root"]
    assert isinstance(cas_root, Path)
    artifact_store = with_ambient_ownership_enforcement_if_supported(FileSystemCAS(cas_root))
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source_data_ref = artifact_store.put_json(
            {"observed": {"employment_rate": 0.5}},
            PutOptions(
                kind="test.control-job-observation",
                media_type="application/json",
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        snapshot_ref = artifact_store.put_json(
            DataSnapshot(data_ref=source_data_ref),
            PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
                ),
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": snapshot_ref.model_dump(mode="json")},
        params={"control_plane_transition": "legacy_shadow"},
    )
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", scoped_scientist_execution)

    with client:
        service = client.app.state.runtime_container.control_service
        assert service is not None
        stop_embedded_control_worker(service)
        unauthenticated = client.post(
            "/api/v1/control/runs",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        assert unauthenticated.status_code == 401, unauthenticated.text
        assert opa.inputs == []

        accepted_response = client.post(
            "/api/v1/control/runs",
            headers=headers,
            json=request.model_dump(mode="json", exclude_none=True),
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        assert accepted["status"] == "accepted"
        observed["job_id"] = accepted["job_id"]
        run_id = accepted["run_id"]

        launch_checks = [
            item
            for item in opa.inputs
            if getattr(item, "action_permission", None) is RuntimePermission.RUNS_LAUNCH
        ]
        assert len(launch_checks) == 1
        assert launch_checks[0].action_resource_class == "runtime.run_collection"
        assert launch_checks[0].resource_tenant_id == tenant_id

        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        terminal = service._control_store.get_job(accepted["job_id"])
        assert terminal is not None
        assert terminal.state == "completed"
        assert terminal.progress["authority_path"] == "legacy_shadow"
        assert terminal.progress["authority_result"] == "candidate_only"
        assert terminal.progress["legacy_path_disposition"] == "candidate_only_ring2_withheld"

        fresh_job = client.get(
            f"/api/v1/control/jobs/{accepted['job_id']}",
            headers=headers,
        )
        assert fresh_job.status_code == 200, fresh_job.text
        assert fresh_job.json()["state"] == "completed"
        fresh_run = client.get(f"/api/v1/runs/{run_id}", headers=headers)
        assert fresh_run.status_code == 200, fresh_run.text
        assert fresh_run.json()["run"]["run_id"] == run_id

        assert observed["tenant_context"] == ArtifactTenantContextInfo(
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
