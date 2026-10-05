"""Served, tenant-bound behavioral proof for the N5 interaction read projection."""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core import security as core_security
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.run.context import RunContext
from polisyos.core.security import tenant_scope
from polisyos.runtime.http.resilience import GuardedDependencyProxy
from polisyos.runtime.http.routes import n5_interaction_diagnostics as route
from polisyos.runtime.http.services.control import generation_cycle as compiled_owner
from polisyos.runtime.quality import generation_cycle as n5_owner
from tests.unit.runtime.http import test_control_service_di as producer_fixture_support
from tests.unit.runtime.http.test_control_service_di import (
    _run_controlled_simulate_only_job_fixture,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)
from tests.unit.runtime.quality import test_generation_cycle as n5_fixture_support


class _CaptureAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)


def _served_semantics(
    payload: dict[str, Any],
    *,
    run_id: str,
    compiled_ref: str,
    n5_ref: str,
) -> None:
    assert payload["run_id"] == run_id
    assert payload["compiled_run_ref"] == compiled_ref
    assert payload["authority_band"] == "candidate"
    assert payload["projection_authority"] == "projection_only"
    assert payload["uncertainty_kind"] == "K_sim"
    assert "promotion" in payload["may_not_use_for"]
    diagnostic = next(
        item for item in payload["diagnostics"] if item["cycle_index"] is not None
    )
    assert diagnostic["simulation_result_ref"] == n5_ref
    assert diagnostic["payload_hash"] == n5_ref
    assert diagnostic["receipt_payload_hash"].startswith("sha256:")
    assert diagnostic["interaction_evidence_status"] == "incomplete"
    assert diagnostic["checked_interaction_orders"] == []
    assert diagnostic["n8_same_ref_association"] == "not_recorded"
    joint = next(item for item in diagnostic["trajectories"] if item["run_level"] == "joint")
    assert joint["expected_steps"] == [0, 1, 2, 3]
    assert joint["observed_steps"] == [0]
    assert joint["missing_steps"] == [1, 2, 3]
    assert joint["extra_steps"] == []
    assert joint["duplicate_steps"] == []
    assert payload["interaction_evidence_status"] == "incomplete"


@pytest.mark.asyncio
async def test_served_n5_projection_binds_tenant_cell_job_and_persisted_bytes(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A real assembled route discloses persisted N5 limits and rejects foreign scope first."""

    app = runtime_api_env["app"]
    context = app.state.runtime_container.runtime_api_context
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    assert isinstance(context.store, GuardedDependencyProxy)
    original_tenant_scope = core_security.tenant_scope

    def runtime_tenant_scope(backend, *, tenant_id: str, cell_id: str | None = None):
        if tenant_id == "tenant-fixture":
            tenant_id = runtime_api_env["tenant_a"]
        if cell_id == "cell-fixture":
            cell_id = runtime_api_env["cell_a"]
        return original_tenant_scope(
            backend,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    with monkeypatch.context() as producer_scope:
        producer_scope.setattr(
            producer_fixture_support,
            "FileSystemCAS",
            lambda _root: context.store,
        )
        producer_scope.setattr(
            producer_fixture_support,
            "_fixture_claims",
            lambda: _claims(
                tenant_id=tenant_id,
                cell_id=cell_id,
                jti="b26-n5-producer",
            ),
        )
        producer_scope.setattr(core_security, "tenant_scope", runtime_tenant_scope)
        from tools.quality.validation import (
            check_layer3_gy_design_generation_contract as n4_contract,
        )

        recording_id = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
        recordings = tuple(
            item
            for item in n4_contract._load_recordings(n5_fixture_support.REPO_ROOT)
            if item.get("design_problem_id") == recording_id
        )
        assert len(recordings) == 1
        recorded_problem = n4_contract._design_problem(recordings[0])
        original_owner_case = n5_fixture_support._cyc01_owner_bound_n5_case

        def owner_case_for_recorded_problem(*, runtime_hints=None, problem_seed=None):
            return original_owner_case(
                runtime_hints=runtime_hints,
                problem_seed=(
                    problem_seed if problem_seed is not None else recorded_problem
                ),
            )

        # The shared served fixture's WMR must be built from the same problem
        # later replayed by its recorded N4 producer. Its default generic-policy
        # seed is not compatible with that recorded CGF problem's domain.
        with monkeypatch.context() as owner_input_scope:
            owner_input_scope.setattr(
                n5_fixture_support,
                "_cyc01_owner_bound_n5_case",
                owner_case_for_recorded_problem,
            )
            producer_fixture = await _run_controlled_simulate_only_job_fixture(
                monkeypatch,
                tmp_path / "n5-producer",
            )
    try:
        control_service = app.state._control_service
        run_id = str(producer_fixture.job.run_id)
        job_id = producer_fixture.job.job_id
        compiled_id = ArtifactID.model_validate(producer_fixture.compiled_ref)
        source_store = producer_fixture.service._artifact_store
        assert source_store is context.store
        assert producer_fixture.service._promotion_runtime.store is context.store
        with tenant_scope(
            None,
            tenant_id=tenant_id,
            cell_id=cell_id,
        ):
            compiled_manifest = source_store.get_manifest(compiled_id)
        compiled_source_ref = ArtifactRef(
            artifact_id=compiled_id,
            kind=compiled_manifest.kind,
            media_type=compiled_manifest.media_type,
        )

        from polisyos.runtime.http.services.control.generation_cycle import (
            CompiledRecursiveGenerationCycleRun,
        )

        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            from_canonical_bytes(producer_fixture.compiled_payload)
        )
        n5_refs: dict[str, ArtifactRef] = {}
        for node in compiled.recursive_run.nodes:
            if node.joint_simulation_ref is not None:
                ref = node.joint_simulation_ref
                n5_refs[str(ref.artifact_id)] = ArtifactRef(
                    artifact_id=ref.artifact_id,
                    kind=ref.kind,
                    media_type=ref.media_type,
                )
            if node.cycle_run is None:
                continue
            for cycle in node.cycle_run.cycles:
                ref = cycle.simulation.simulation_result_ref
                if ref is not None:
                    n5_refs[str(ref.artifact_id)] = ArtifactRef(
                        artifact_id=ref.artifact_id,
                        kind=ref.kind,
                        media_type=ref.media_type,
                    )
        assert n5_refs

        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            for ref in (*n5_refs.values(), compiled_source_ref):
                manifest = context.store.get_manifest(ref)
                assert manifest.tenant_context is not None
                assert manifest.tenant_context.tenant_id == tenant_id
                assert manifest.tenant_context.cell_id == cell_id
                assert manifest.artifact_id == ref.artifact_id
            for ref in n5_refs.values():
                persisted_n5 = n5_owner.load_joint_simulation_result(
                    ref,
                    store=context.store,
                )
                assert persisted_n5.uncertainty_kind == "K_sim"
            compiled_ref = compiled_source_ref
            registry_ref = context.store.put_json(
                {"registry": {}},
                ArtifactWriteOptions(
                    kind="core.registry_bundle",
                    media_type="application/json",
                    tenant_context=ArtifactTenantContextInfo(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    ),
                ),
            )
            payload_ref = context.store.put_json(
                {"tenant_id": tenant_id, "cell_id": cell_id, "run_id": run_id},
                ArtifactWriteOptions(
                    kind="runtime.control_job_payload.natural_language_run",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.runtime.ControlJobPayload",
                        version="1.0",
                    ),
                    tenant_context=ArtifactTenantContextInfo(
                        tenant_id=tenant_id,
                        cell_id=cell_id,
                    ),
                ),
            )
            run = RunContext.start(
                context.store,
                registry_ref,
                run_dir=context.core_runs_root / run_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            run.run_manifest.control_job_id = job_id
            run.add_output(compiled_ref)
            run.finalize(status="completed")

        control_store = control_service._control_store
        capability_ref = str(runtime_api_env["capability_manifest_artifact_id"])
        control_store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=capability_ref,
            payload_ref=str(payload_ref.artifact_id),
            submitted_by="b26-n5-projection-test",
        )
        control_store.complete_job(
            job_id=job_id,
            run_id=run_id,
            capability_manifest_ref=capability_ref,
            progress={
                "state": "completed",
                "phase": "natural_language_run",
                "run_id": run_id,
                "compiled_recursive_generation_cycle_ref": str(
                    compiled_ref.artifact_id
                ),
            },
        )
        context.run_index.refresh(force=True)

        events: list[str] = []
        original_terminal = route.load_terminal_core_run_source
        original_compiled = route.load_compiled_recursive_generation_cycle_run
        original_n5 = n5_owner.load_joint_simulation_result
        original_latest_job = control_service.get_latest_job_for_run

        def tracked_terminal(*args, **kwargs):
            events.append("terminal")
            return original_terminal(*args, **kwargs)

        def tracked_compiled(*args, **kwargs):
            events.append("compiled")
            return original_compiled(*args, **kwargs)

        def tracked_n5(*args, **kwargs):
            events.append("n5")
            return original_n5(*args, **kwargs)

        def tracked_latest_job(*args, **kwargs):
            events.append("job")
            return original_latest_job(*args, **kwargs)

        monkeypatch.setattr(route, "load_terminal_core_run_source", tracked_terminal)
        monkeypatch.setattr(
            route,
            "load_compiled_recursive_generation_cycle_run",
            tracked_compiled,
        )
        monkeypatch.setattr(n5_owner, "load_joint_simulation_result", tracked_n5)
        monkeypatch.setattr(
            control_service,
            "get_latest_job_for_run",
            tracked_latest_job,
        )

        audit = _CaptureAudit()
        app.state.runtime_container.runtime_access_audit = audit
        app.state.runtime_access_audit = audit
        endpoint = f"/api/v1/runs/{run_id}/n5-interaction-diagnostics"
        response = runtime_api_env["client"].get(endpoint)
        assert response.status_code == 200, response.text
        n5_ref = next(
            item["simulation_result_ref"]
            for item in response.json()["diagnostics"]
            if item["cycle_index"] is not None
        )
        _served_semantics(
            response.json(),
            run_id=run_id,
            compiled_ref=str(compiled_ref.artifact_id),
            n5_ref=n5_ref,
        )
        assert events.index("terminal") < events.index("job")
        assert events.index("job") < events.index("compiled")
        assert events.index("compiled") < events.index("n5")
        read_audits = [
            item
            for item in audit.entries
            if item.get("resource_kind") == "runtime.run.n5_interaction_diagnostics"
        ]
        assert len(read_audits) == 1
        assert read_audits[0]["tenant_id"] == tenant_id
        assert read_audits[0]["resource_id"] == run_id

        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            persisted_rows, _status, _limitations = (
                compiled_owner.project_compiled_n5_interaction_diagnostics(
                    compiled,
                    store=context.store,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
            )
        marker_source = next(row for row in persisted_rows if row.cycle_index is not None)
        marker_only_rows = (
            marker_source.model_copy(
                update={
                    "interaction_evidence_status": "complete",
                    "expected_steps": (0, 1, 2, 3),
                    "checked_interaction_orders": (1, 2),
                    "issues": (),
                    "reconciliation_issues": (),
                    "trajectories": (),
                }
            ),
        )

        def marker_only_projection(*args, **kwargs):
            return marker_only_rows, "complete", ()

        with monkeypatch.context() as removal_probe:
            removal_probe.setattr(
                route,
                "project_compiled_n5_interaction_diagnostics",
                marker_only_projection,
            )
            removed = runtime_api_env["client"].get(endpoint)
            assert removed.status_code == 200, removed.text
            with pytest.raises(AssertionError):
                _served_semantics(
                    removed.json(),
                    run_id=run_id,
                    compiled_ref=str(compiled_ref.artifact_id),
                    n5_ref=n5_ref,
                )

        control = runtime_api_env["client"].get(endpoint)
        assert control.status_code == 200, control.text
        _served_semantics(
            control.json(),
            run_id=run_id,
            compiled_ref=str(compiled_ref.artifact_id),
            n5_ref=n5_ref,
        )

        denied_reads: list[str] = []
        original_resolve_control = route.resolve_control_service

        def count_denied_read(name: str, original):
            def wrapped(*args, **kwargs):
                denied_reads.append(name)
                return original(*args, **kwargs)

            return wrapped

        monkeypatch.setattr(
            route,
            "load_terminal_core_run_source",
            count_denied_read("terminal", original_terminal),
        )
        monkeypatch.setattr(
            route,
            "resolve_control_service",
            count_denied_read("job", original_resolve_control),
        )
        monkeypatch.setattr(
            route,
            "load_compiled_recursive_generation_cycle_run",
            count_denied_read("compiled", original_compiled),
        )
        monkeypatch.setattr(
            n5_owner,
            "load_joint_simulation_result",
            count_denied_read("n5", original_n5),
        )
        for token_tenant in (tenant_id, runtime_api_env["tenant_b"]):
            secure_client, cell, provider = _build_secure_client(
                runtime_api_env,
                opa_client=_AllowOPA(),
                claims_by_token={},
                raise_server_exceptions=False,
            )
            bearer = _fixture_bearer(f"b26-n5-scope-{token_tenant}-{cell.cell_id}")
            provider.put_claim(
                bearer,
                _claims(
                    tenant_id=token_tenant,
                    cell_id=cell.cell_id,
                    jti=f"jwt-{token_tenant}-{cell.cell_id}",
                ),
            )
            denied = secure_client.get(
                endpoint,
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "X-Tenant-ID": token_tenant,
                },
            )
            assert denied.status_code in {403, 404}, denied.text
        assert denied_reads == []

        unknown = runtime_api_env["client"].get(
            "/api/v1/runs/b26-unknown-run/n5-interaction-diagnostics"
        )
        assert unknown.status_code == 404, unknown.text
        assert denied_reads == []
    finally:
        producer_fixture.service.close()
