from __future__ import annotations

import importlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core.components import ComponentId
from polisyos.core.contracts.control import (
    LexTriggerRequest,
    NaturalLanguageRunRequest,
    PolicyFlags,
    WorkflowRunRequest,
)
from polisyos.pdc._impl.gy_waist import ArtifactRef
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.resilience import GuardedDependencyProxy
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.quality.evaluation_modes import resolve_evaluation_mode
from polisyos.runtime.quality.evaluation_safety import EvaluationAttemptIntake
from tests._helpers.control_worker import dispatch_one_control_job
from tests.unit.runtime.http.control_service_test_support import (
    bound_nl_authorization_proof,
)
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _fixture_claims,
)


def _create_legacy_workflow_job(
    service: ControlPlaneService,
    *,
    job_id: str,
    run_id: str,
    payload: dict[str, object],
) -> str:
    """Create a pre-scope workflow row with an old-format creation envelope."""
    from polisyos.core.security.tenant_context import clear_tenant_context

    with clear_tenant_context():
        payload_ref = service._persist_job_payload(  # noqa: SLF001
            job_kind="workflow_run",
            payload=payload,
        )
    policy_flags = PolicyFlags().model_dump(mode="json")
    service._control_store.create_job(  # noqa: SLF001
        job_id=job_id,
        kind="workflow_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags=policy_flags,
        capability_manifest_ref=None,
        payload_ref=payload_ref,
        submitted_by="legacy-r14",
        creation_event_payload={
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": "workflow_run",
            "pipeline_id": None,
            "payload_ref": payload_ref,
            "submitted_by": "legacy-r14",
            "requested_execution_profile": None,
            "effective_execution_profile": "dev",
            "policy_flags": policy_flags,
            "capability_manifest_ref": None,
            # Older rows have no typed scope. Payload fields cannot fill this gap.
        },
    )
    return payload_ref


def test_unknown_scope_payload_identity_is_cleared_before_transition_stub(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )

    service = _build_control_service(tmp_path)
    job_id = "job-r14-legacy-unclaimed-candidate"
    run_id = "run-r14-legacy-unclaimed-candidate"
    forged_identity = {
        "tenant_id": "tenant-poisoned-a",
        "cell_id": "cell-poisoned-a",
        "job_id": "job-payload-forged",
        "run_id": "run-payload-forged",
        "runtime_identity": {
            "tenant_id": "tenant-runtime-forged",
            "cell_id": "cell-runtime-forged",
            "job_id": "job-runtime-forged",
            "run_id": "run-runtime-forged",
        },
    }
    payload = {
        **forged_identity,
        "run_id": run_id,
        "state_payload": {
            "run_id": run_id,
            "inputs": {},
            **forged_identity,
            "params": dict(forged_identity),
        },
        "checkpoint_policy": None,
    }
    try:
        _create_legacy_workflow_job(
            service,
            job_id=job_id,
            run_id=run_id,
            payload=payload,
        )
        reads: list[tuple[str | None, str | None, object]] = []
        original_load = service._load_payload_ref  # noqa: SLF001

        def observe_scope_on_reads(ref: str):
            reads.append(
                (
                    get_current_tenant_id_or_none(),
                    get_current_cell_id(),
                    get_current_access_scope_or_none(),
                )
            )
            return original_load(ref)

        monkeypatch.setattr(service, "_load_payload_ref", observe_scope_on_reads)
        transition_calls: list[dict[str, object]] = []

        def run_unclaimed_candidate(state_payload, _checkpoint_policy, **_kwargs):
            # This probe checks identity sanitization only; the served candidate
            # limitation and persisted readback are tested on the real workflow.
            transition_calls.append(dict(state_payload))
            return {"status": "transition_stub_completed"}

        monkeypatch.setattr(
            service,
            "_execute_workflow_control_transition",
            run_unclaimed_candidate,
        )
        monkeypatch.setattr(
            service,
            "_finalize_workspace_loop_run_proof",
            lambda **_kwargs: None,
        )
        poison = AccessScope.for_service(
            tenant_id="tenant-poisoned-a",
            cell_id="cell-poisoned-a",
            spiffe_id="spiffe://r14/unknown-scope-poison",
        )
        with tenant_scope(
            None,
            tenant_id="tenant-poisoned-a",
            cell_id="cell-poisoned-a",
        ):
            token = set_current_access_scope(poison)
            try:
                dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=job_id,
                )
            finally:
                reset_current_access_scope(token)

        completed = service.get_job_status(job_id)
        assert completed.state == "completed"
        assert transition_calls
        sanitized = transition_calls[0]
        assert sanitized["job_id"] == job_id
        assert sanitized["run_id"] == run_id
        assert not {"tenant_id", "cell_id", "runtime_identity"}.intersection(sanitized)
        assert not {
            "tenant_id",
            "cell_id",
            "job_id",
            "run_id",
            "runtime_identity",
        }.intersection(sanitized["params"])
        assert reads
        assert all(tenant is None and cell is None and scope is None for tenant, cell, scope in reads)

        current = service._control_store.get_job(job_id)  # noqa: SLF001
        assert current is not None and current.capability_manifest_ref
        manifest = original_load(current.capability_manifest_ref)
        actor = manifest["actor"]
        assert actor["subject"] == "anonymous"
        assert actor["authenticated"] is False
        assert actor["tenant_id"] is None
        assert actor["cell_id"] is None
        assert actor["roles"] == []
    finally:
        service.close()


def test_unknown_scope_cannot_use_matching_ambient_tenant_for_owned_payload(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
        reset_current_access_scope,
        set_current_access_scope,
        tenant_scope,
    )

    service = runtime_api_env["app"].state._control_service
    if service._worker is not None:
        service._worker.stop()
    control_routes = importlib.import_module("polisyos.runtime.http.routes.control")
    monkeypatch.setattr(control_routes, "_get_principal", lambda _request: RuntimePrincipal())
    # Keep the runtime-supplied GuardedDependencyProxy; unwrapping this method
    # returns its raw CAS and would bypass the executor/context boundary under test.
    guarded_store = service._artifact_store  # noqa: SLF001
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "data_source": {
                "data_snapshot_ref": runtime_api_env["root_artifact_id"]
            },
            "params": {
                "slice0_fixture_id": "ua_msme_credit_worldbank_measurement",
                "tenant_id": runtime_api_env["tenant_a"],
                "cell_id": runtime_api_env["cell_a"],
            },
        },
    )
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    job = service._control_store.get_job(job_id)  # noqa: SLF001
    assert job is not None and job.payload_ref is not None
    try:
        guarded_store.record_artifact_owner(
            job.payload_ref,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            writer="test_unknown_scope_cannot_use_matching_ambient_tenant_for_owned_payload",
        )
        reads: list[tuple[str, str | None, str | None, object]] = []
        ownership_errors: list[ArtifactOwnershipError] = []
        original_load = service._load_payload_ref  # noqa: SLF001

        def observe_scope_before_read(ref: str):
            reads.append(
                (
                    ref,
                    get_current_tenant_id_or_none(),
                    get_current_cell_id(),
                    get_current_access_scope_or_none(),
                )
            )
            try:
                return original_load(ref)
            except ArtifactOwnershipError as error:
                ownership_errors.append(error)
                raise

        monkeypatch.setattr(service, "_load_payload_ref", observe_scope_before_read)
        refresh_calls: list[str] = []

        def observe_refresh(**kwargs):
            refresh_calls.append(kwargs["job"].job_id)
            raise AssertionError("payload denial must precede manifest refresh")

        monkeypatch.setattr(service, "_refresh_capability_manifest", observe_refresh)
        transition_calls: list[bool] = []
        monkeypatch.setattr(
            service,
            "_execute_workflow_control_transition",
            lambda *_args, **_kwargs: transition_calls.append(True),
        )
        poison = AccessScope.for_service(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
            spiffe_id="spiffe://r14/unknown-owner-negative",
        )
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            token = set_current_access_scope(poison)
            try:
                assert get_current_tenant_id_or_none() == runtime_api_env["tenant_a"]
                assert get_current_cell_id() == runtime_api_env["cell_a"]
                assert get_current_access_scope_or_none() == poison
                dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=job_id,
                )
            finally:
                reset_current_access_scope(token)

        failed = service.get_job_status(job_id)
        assert failed.state == "failed"
        assert transition_calls == []
        assert refresh_calls == []
        assert reads == [(job.payload_ref, None, None, None)]
        assert len(ownership_errors) == 1
    finally:
        if service._worker is not None:
            service._worker.stop()


def test_capability_manifest_binding_is_type_strict_and_role_exact(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal(
        subject="user-fixture",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        roles=frozenset({"analyst", "researcher"}),
        authenticated=True,
    )
    try:
        launch = service.launch_workflow_run(
            WorkflowRunRequest(
                data_source={"data_snapshot_ref": "sha256:" + "a" * 64}
            ),
            principal=principal,
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None and job.capability_manifest_ref is not None
        manifest = service._load_payload_ref(job.capability_manifest_ref)  # noqa: SLF001
        policy = service._resolve_execution_policy(  # noqa: SLF001
            requested_profile=job.requested_execution_profile,
            policy_flags=PolicyFlags.model_validate(job.policy_flags),
            principal=principal,
        )
        execution_scope = service._execution_scope_for_policy(policy)  # noqa: SLF001

        def reverse_object_keys(value):
            if isinstance(value, dict):
                return {
                    key: reverse_object_keys(value[key])
                    for key in reversed(tuple(value))
                }
            if isinstance(value, list):
                return [reverse_object_keys(item) for item in value]
            return value

        reordered_ref = service._put_json_artifact(  # noqa: SLF001
            reverse_object_keys(manifest),
            kind="runtime.capability_manifest",
            schema_name="polisyos.runtime.CapabilityManifest",
        )
        assert service._validate_capability_manifest_for_scope(  # noqa: SLF001
            manifest_ref=reordered_ref,
            job=job,
            execution_scope=execution_scope,
        )["actor"] == manifest["actor"]

        boolean_key = next(
            key
            for key, value in manifest["policy_flags"].items()
            if type(value) is bool
        )
        malformed_manifests = []
        malformed_policy = deepcopy(manifest)
        malformed_policy["policy_flags"][boolean_key] = int(
            malformed_policy["policy_flags"][boolean_key]
        )
        malformed_manifests.append(
            (malformed_policy, "control_job_capability_manifest_binding_mismatch")
        )

        malformed_roles = deepcopy(manifest)
        roles = malformed_roles["actor"]["roles"]
        malformed_roles["actor"]["roles"] = [*roles, *roles]
        malformed_manifests.append(
            (malformed_roles, "control_job_capability_manifest_actor_mismatch")
        )

        reordered_roles = deepcopy(manifest)
        reordered_roles["actor"]["roles"] = list(reversed(roles))
        malformed_manifests.append(
            (reordered_roles, "control_job_capability_manifest_actor_mismatch")
        )

        malformed_role_type = deepcopy(manifest)
        malformed_role_type["actor"]["roles"] = [
            *malformed_role_type["actor"]["roles"],
            False,
        ]
        malformed_manifests.append(
            (malformed_role_type, "control_job_capability_manifest_actor_mismatch")
        )

        for malformed, expected_error in malformed_manifests:
            malformed_ref = service._put_json_artifact(  # noqa: SLF001
                malformed,
                kind="runtime.capability_manifest",
                schema_name="polisyos.runtime.CapabilityManifest",
            )
            with pytest.raises(RuntimeError, match=expected_error):
                service._validate_capability_manifest_for_scope(  # noqa: SLF001
                    manifest_ref=malformed_ref,
                    job=job,
                    execution_scope=execution_scope,
                )
    finally:
        service.close()


def test_execution_scope_issuer_rejects_malformed_identity_without_normalizing(
    tmp_path,
) -> None:
    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal(
        subject="user-fixture",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        roles=frozenset({"analyst", "researcher"}),
        authenticated=True,
    )
    try:
        policy = service._resolve_execution_policy(  # noqa: SLF001
            requested_profile="dev",
            policy_flags=PolicyFlags(),
            principal=principal,
        )
        canonical_scope = service._execution_scope_for_policy(policy)  # noqa: SLF001
        assert canonical_scope.status == "established"
        assert canonical_scope.actor_roles == ("analyst", "researcher")

        malformed_actors = [
            (
                "padded_role",
                {**policy.actor, "roles": [" admin "]},
            ),
            (
                "duplicate_roles",
                {**policy.actor, "roles": ["analyst", "analyst"]},
            ),
            (
                "nonstr_role",
                {**policy.actor, "roles": ["analyst", False]},
            ),
            (
                "unsorted_roles",
                {**policy.actor, "roles": ["researcher", "analyst"]},
            ),
            (
                "padded_subject",
                {**policy.actor, "subject": " user-fixture"},
            ),
            (
                "padded_tenant",
                {**policy.actor, "tenant_id": " tenant-fixture"},
            ),
            (
                "padded_cell",
                {**policy.actor, "cell_id": "cell-fixture "},
            ),
        ]
        for case, actor in malformed_actors:
            scope = service._execution_scope_for_policy(  # noqa: SLF001
                replace(policy, actor=actor)
            )
            assert scope.status == "not_established", case
            assert scope.tenant_id is None, case
            assert scope.cell_id is None, case
            assert scope.actor_subject is None, case
            assert scope.actor_authenticated is False, case
            assert scope.actor_roles == (), case
    finally:
        service.close()


def test_lex_worker_keeps_completion_diagnostic_under_admitted_scope(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)

    async def completed_pipeline(_config: object) -> None:
        return None

    monkeypatch.setattr(
        "polisyos.data_forge.read_api.legal.run_batch_pipeline",
        completed_pipeline,
    )
    try:
        launch = service.trigger_lex_pipeline(
            LexTriggerRequest(
                cards_path=str(tmp_path / "cards.json"),
                texts_path=str(tmp_path / "texts"),
                output_dir=str(tmp_path / "lex-output"),
                stages={"parse": True, "structure": False, "spo": False, "graph": False, "embed": False},
            ),
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
        )
        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None and job.state == "completed"
        event = next(
            record
            for record in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=launch.job_id
            )
            if record.event.phase == "lex_pipeline"
            and record.event.state_after == "completed"
        )
        assert event.event.tenant_id == _fixture_claims().tenant_id
        assert event.event.cell_id == _fixture_claims().cell_id
        assert event.payload_inline is not None
        assert event.payload_inline["execution_scope"]["status"] == "established"
        assert event.payload_inline["execution_scope"]["source"] == "job_admission"
    finally:
        service.close()


def test_approval_hook_persists_typed_limitation_when_request_scope_is_incomplete(
    tmp_path,
) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import tenant_scope

    service = _build_control_service(tmp_path)
    run_id = "run-r14-approval-diagnostic-scope"
    job_id = "job-r14-approval-diagnostic-scope"
    try:
        service._control_store.create_job(  # noqa: SLF001
            job_id=job_id,
            kind="workflow_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="test-approval-projection",
        )
        service._control_store.complete_job(  # noqa: SLF001
            job_id=job_id,
            run_id=run_id,
            progress={"state": "completed"},
        )
        incomplete_scope = AccessScope.for_service(
            tenant_id="tenant-request-owner",
            cell_id=None,
            spiffe_id="spiffe://r14/approval-hook",
        )
        with tenant_scope(
            None,
            tenant_id="tenant-request-owner",
            cell_id="cell-ambient-poison",
        ):
            service.record_production_approval_packet(
                run_id=run_id,
                approval_packet_ref="sha256:" + "f" * 64,
                decision="approved",
                request_access_scope=incomplete_scope,
            )

        event = next(
            record
            for record in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=job_id
            )
            if record.event.event_type == "polisyos.runtime.diagnostic.scope_limited.v1"
        )
        assert event.event.tenant_id == "tenant-unknown"
        assert event.event.cell_id == "cell-unknown"
        assert event.event.state_after == "not_established"
        assert event.payload_ref is None
        assert event.event.payload_ref is None
        assert event.event.artifact_refs == ()
        assert event.event.input_refs == ()
        assert event.payload_inline == {
            "execution_scope": {
                "schema_version": "polisyos.runtime.control_execution_scope.v1",
                "status": "not_established",
                "source": "authenticated_request",
                "limitation_code": "control_job_execution_scope_not_established",
            },
            "withheld_event_type": "polisyos.runtime.diagnostic.approval_decision.v1",
            "authority_status": "withheld",
            "limitation_code": "control_job_execution_scope_not_established",
        }
    finally:
        service.close()


def test_approval_hook_emits_event_from_verified_request_scope(tmp_path) -> None:
    from polisyos.core.security.access_scope import AccessScope
    from polisyos.core.security.tenant_context import tenant_scope

    service = _build_control_service(tmp_path)
    run_id = "run-r14-approval-diagnostic-established"
    job_id = "job-r14-approval-diagnostic-established"
    tenant_id = "tenant-request-owner"
    cell_id = "cell-request-owner"
    try:
        service._control_store.create_job(  # noqa: SLF001
            job_id=job_id,
            kind="workflow_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=None,
            submitted_by="test-approval-projection",
        )
        service._control_store.complete_job(  # noqa: SLF001
            job_id=job_id,
            run_id=run_id,
            progress={"state": "completed"},
        )
        request_scope = AccessScope.for_service(
            tenant_id=tenant_id,
            cell_id=cell_id,
            spiffe_id="spiffe://r14/approval-hook",
        )
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            service.record_production_approval_packet(
                run_id=run_id,
                approval_packet_ref="sha256:" + "e" * 64,
                decision="approved",
                request_access_scope=request_scope,
            )

        event = next(
            record
            for record in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=job_id
            )
            if record.event.event_type
            == "polisyos.runtime.diagnostic.approval_decision.v1"
        )
        assert event.event.tenant_id == tenant_id
        assert event.event.cell_id == cell_id
        assert event.event.state_after == "approved"
        assert event.payload_ref is not None
    finally:
        service.close()


def test_unknown_scope_acquisition_refuses_before_route_owner_or_effect_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
        AcquisitionActionServiceError,
    )
    from polisyos.runtime.http.services.control_plane_store import ControlJobExecutionScope

    service = object.__new__(AcquisitionActionService)
    calls: list[str] = []
    service._execution_port = object()
    monkeypatch.setattr(
        service,
        "_validated_mutation",
        lambda **_kwargs: calls.append("owner-resolution"),
        raising=False,
    )
    unknown_scope = ControlJobExecutionScope(
        status="not_established",
        tenant_id=None,
        cell_id=None,
        actor_subject=None,
        actor_authenticated=False,
        actor_roles=(),
    )

    with pytest.raises(
        AcquisitionActionServiceError,
        match="acquisition_job_owner_scope_not_established",
    ):
        service.handle_job(
            SimpleNamespace(kind="acquisition", run_id="run-r14-unknown-acquisition"),
            {
                "tenant_id": "tenant-poisoned-a",
                "cell_id": "cell-poisoned-a",
                "route_id": "sha256:" + "a" * 64,
                "request": {},
            },
            unknown_scope,
        )

    assert calls == []


def _artifact_ref(kind: str, digit: str) -> ArtifactRef:
    digest = "sha256:" + digit * 64
    return ArtifactRef(
        artifact_id=digest,
        artifact_type=kind,
        content_hash=digest,
        schema_ref=f"{kind}.v1",
        uri=f"cas://sha256/{digest.removeprefix('sha256:')}",
        version="1.0",
    )


def _field_pilot_intake() -> EvaluationAttemptIntake:
    requested_at = datetime.now(UTC)
    return EvaluationAttemptIntake(
        attempt_id="attempt-r5-durable-intent",
        evaluator_owner_id=ComponentId("polisyos.runtime.quality.foundry_value_port@1.0.0"),
        design_problem_ref="sha256:" + "1" * 64,
        candidate_ref=_artifact_ref("test.candidate", "2"),
        world_model_record_ref=_artifact_ref("test.world_model_record", "3"),
        requested_mode_token="field_pilot",  # noqa: S106
        mode_resolution=resolve_evaluation_mode("field_pilot"),
        domain_hint=None,
        domain_pack_ref=None,
        target_population_scope_ref=_artifact_ref("test.population", "4"),
        evaluation_input_refs=(),
        evaluation_input_provenance=(),
        evidence_refs=(),
        requested_at=requested_at,
        intended_start_at=requested_at,
        requested_rule_version=None,
        external_executor_identity_ref=None,
    )


def _job_created_event(service, job_id: str) -> tuple[int, dict[str, object]]:
    with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
        rows = connection.execute(
            "SELECT event_id, payload_json FROM control_job_events "
            "WHERE job_id = ? AND event_type = 'job_created' ORDER BY event_id",
            (job_id,),
        ).fetchall()
    assert len(rows) == 1
    return int(rows[0][0]), json.loads(str(rows[0][1]))


def _outbox_payload(service, job_id: str) -> dict[str, object]:
    record = service._control_store.get_job_created_outbox_event(job_id)  # noqa: SLF001
    assert record is not None
    return dict(record.payload)


def _valid_intake_for_mode(mode: str) -> EvaluationAttemptIntake:
    original = _field_pilot_intake()
    return original.model_copy(
        update={
            "requested_mode_token": mode,
            "mode_resolution": resolve_evaluation_mode(mode),
        }
    )


@pytest.mark.asyncio
async def test_plain_nl_job_persists_candidate_intent_and_reaches_candidate_compiler(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Explore a policy option as a candidate.",
            llm_model="simulated-qwen",
            run_budget_usd=2.0,
            per_model_budget_usd=1.0,
            execution_plan={
                "stop_criteria": {"min_delta_improvement": 0.01},
            },
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        status = service.get_job_status(launch.job_id)
        assert record.state == status.state == "pending"
        assert record.progress["state"] == status.progress["state"] == "pending"
        assert service._control_store.list_job_state_transitions(launch.job_id) == [  # noqa: SLF001
            "pending"
        ]
        created_event = service._control_store.get_job_created_event_payload(  # noqa: SLF001
            launch.job_id
        )
        assert created_event["state"] == "pending"
        outbox_payload = _outbox_payload(service, launch.job_id)
        assert outbox_payload["state"] == "pending"
        pending_admission_transitions = [
            item.event
            for item in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=launch.job_id
            )
            if item.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
        ]
        assert len(pending_admission_transitions) == 1
        assert pending_admission_transitions[0].state_after == "pending"
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        _, created_event = _job_created_event(service, launch.job_id)

        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == "candidate_only"
        assert created_event.get("execution_intent_binding") == binding
        assert created_event.get("payload_ref") == record.payload_ref
        outbox_payload = _outbox_payload(service, launch.job_id)
        assert outbox_payload.get("execution_intent_binding") == binding
        assert outbox_payload.get("payload_ref") == record.payload_ref

        compiler_intents: list[str | None] = []

        async def compiler_probe(**kwargs: object) -> object:
            compiler_intents.append(
                str(kwargs.get("execution_intent"))
                if kwargs.get("execution_intent") is not None
                else None
            )
            raise RuntimeError("candidate_control_reached_compiler")

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None
        assert compiler_intents == ["candidate_only"]
        assert completed.error_message == "candidate_control_reached_compiler"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_nl_launch_requires_served_proof_for_candidate_and_protected_requests(
    tmp_path,
) -> None:
    service = _build_control_service(tmp_path)
    principal = RuntimePrincipal.from_user_claims(_fixture_claims())
    try:
        with pytest.raises(ValueError, match="nl_route_authorization_proof_not_established"):
            await service.launch_nl_run(
                NaturalLanguageRunRequest(
                    request="A direct service launch must carry the route proof.",
                    llm_model="simulated-qwen",
                ),
                principal=principal,
            )

        with pytest.raises(ValueError, match="nl_route_authorization_proof_not_established"):
            await service.launch_nl_run(
                NaturalLanguageRunRequest(
                    request="A protected service launch must carry the route proof.",
                    llm_model="simulated-qwen",
                    context={
                        "evaluation_safety_attempt": _field_pilot_intake().model_dump(
                            mode="json"
                        )
                    },
                ),
                principal=principal,
            )

    finally:
        service.close()


@pytest.mark.asyncio
async def test_served_authorization_proof_binds_exact_body_and_query_bytes(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    principal = RuntimePrincipal.from_user_claims(claims)
    request = NaturalLanguageRunRequest(
        request="Bind the authorization proof to this exact request.",
        llm_model="simulated-qwen",
    )
    proof = bound_nl_authorization_proof(claims, request)
    try:
        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request.model_copy(update={"request": "A substituted request."}),
                principal=principal,
                authorization_proof=proof,
            )

        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
                authorization_request_body=b"",
            )

        with pytest.raises(ValueError, match="nl_route_authorization_resource_digest_mismatch"):
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
                authorization_query_bytes=b"tenant_id=foreign",
            )

        foreign_principal = RuntimePrincipal(
            subject="user-foreign",
            tenant_id=claims.tenant_id,
            cell_id=claims.cell_id,
            roles=principal.roles,
            authenticated=True,
        )
        with pytest.raises(ValueError, match="nl_route_authorization_actor_binding_mismatch"):
            await service.launch_nl_run(
                request,
                principal=foreign_principal,
                authorization_proof=proof,
            )

        foreign_tenant_principal = RuntimePrincipal(
            subject=principal.subject,
            tenant_id="tenant-foreign",
            cell_id=principal.cell_id,
            roles=principal.roles,
            authenticated=True,
        )
        with pytest.raises(ValueError, match="nl_route_authorization_actor_binding_mismatch"):
            await service.launch_nl_run(
                request,
                principal=foreign_tenant_principal,
                authorization_proof=proof,
            )
    finally:
        service.close()


def test_nl_request_snapshot_digest_profile_accepts_float_and_type_key() -> None:
    from polisyos.runtime.http.services.control.run_lifecycle import (
        _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        _NL_REQUEST_SNAPSHOT_SCHEMA,
        _nl_request_snapshot_content_hash,
    )

    snapshot = {
        "schema_version": _NL_REQUEST_SNAPSHOT_SCHEMA,
        "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
        "request": {
            "context": {"_type": "caller-owned-context-key"},
            "run_budget_usd": 2.0,
        },
        "normalized_llm_models": ["simulated-qwen"],
    }

    digest = _nl_request_snapshot_content_hash(snapshot)

    assert digest == (
        "sha256:56ab3d64aaacfd3fc0175f89f499c10f31f9082d2191181e3635f7082a615ded"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "nonfinite_value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
async def test_served_launch_rejects_nonfinite_context_before_enqueue(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    nonfinite_value: float,
) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    principal = RuntimePrincipal.from_user_claims(claims)
    compiler_calls: list[str] = []
    enqueue_calls: list[str] = []
    original_enqueue = service._enqueue_job  # noqa: SLF001

    async def compiler_probe(**_kwargs: object) -> object:
        compiler_calls.append("candidate_compiler")
        raise RuntimeError("nonfinite_candidate_reached_compiler")

    def enqueue_probe(**kwargs: object) -> object:
        enqueue_calls.append("enqueue")
        return original_enqueue(**kwargs)  # noqa: SLF001

    monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
    monkeypatch.setattr(service, "_enqueue_job", enqueue_probe)  # noqa: SLF001
    try:
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            before_count = int(connection.execute("SELECT COUNT(*) FROM control_jobs").fetchone()[0])

        request = NaturalLanguageRunRequest(
            request="A non-finite context must not be silently normalized into a candidate.",
            llm_model="simulated-qwen",
            context={"measurement": nonfinite_value},
        )
        proof = bound_nl_authorization_proof(claims, request)
        with pytest.raises(RuntimeHTTPError) as raised:
            await service.launch_nl_run(
                request,
                principal=principal,
                authorization_proof=proof,
            )

        assert raised.value.code == "authorization_binding_selector_invalid"
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            after_count = int(connection.execute("SELECT COUNT(*) FROM control_jobs").fetchone()[0])
        assert after_count == before_count
        assert enqueue_calls == []
        assert compiler_calls == []
    finally:
        service.close()


@pytest.mark.asyncio
async def test_float_snapshot_tamper_fails_before_worker_with_markers_intact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    request = NaturalLanguageRunRequest(
        request="Keep the exact numeric request bound to its served authorization proof.",
        llm_model="simulated-qwen",
        run_budget_usd=2.0,
        per_model_budget_usd=1.0,
        execution_plan={
            "stop_criteria": {"min_delta_improvement": 0.01},
        },
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        reached: list[str] = []

        async def compiler_probe(**_kwargs: object) -> object:
            reached.append("candidate_compiler")
            raise RuntimeError("tampered_request_reached_candidate_compiler")

        original_load = service._load_payload_ref  # noqa: SLF001

        def load_tampered_request(payload_ref: str) -> dict[str, object]:
            value = original_load(payload_ref)
            if payload_ref == record.payload_ref:
                snapshot = value.get("nl_request_snapshot")
                assert isinstance(snapshot, dict)
                request_data = snapshot.get("request")
                assert isinstance(request_data, dict)
                request_data["run_budget_usd"] = 3.0
                # Keep the authorization receipt and all intent/event markers intact.
                assert value.get("nl_authorization_receipt")
                assert value.get("execution_intent_binding")
            return value

        monkeypatch.setattr(service, "_load_payload_ref", load_tampered_request)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", compiler_probe)
        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        terminal = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert terminal is not None
        assert terminal.state == "failed"
        assert terminal.error_message == "nl_job_execution_intent_not_established"
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tamper",
    [
        "event_missing",
        "event_mismatched",
        "outbox_missing",
        "outbox_mismatched",
        "capability_actor_mismatched",
        "payload_authorization_receipt_missing",
        "payload_authorization_receipt_foreign",
    ],
)
async def test_protected_intent_event_tamper_blocks_before_evaluation_safety_or_n4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Evaluate this candidate for a field pilot.",
            llm_model="simulated-qwen",
            context={
                "evaluation_safety_attempt": _field_pilot_intake().model_dump(
                    mode="json"
                )
            },
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == "eval_safety_required"

        event_id, created_event = _job_created_event(service, launch.job_id)
        if tamper == "event_missing":
            created_event.pop("execution_intent_binding", None)
        elif tamper == "event_mismatched":
            event_binding = created_event.get("execution_intent_binding")
            assert isinstance(event_binding, dict)
            event_binding["intent_band"] = "candidate_only"
        with service._control_store._sqlite_connection() as connection:  # noqa: SLF001
            if tamper.startswith("event_"):
                connection.execute(
                    "UPDATE control_job_events SET payload_json = ? "
                    "WHERE event_id = ? AND job_id = ? AND event_type = 'job_created'",
                    (json.dumps(created_event, sort_keys=True), event_id, launch.job_id),
                )
            elif tamper.startswith("outbox_"):
                row = connection.execute(
                    "SELECT event_id, payload_json FROM control_outbox_events "
                    "WHERE topic = 'control.job.created' AND event_key = ? AND job_id = ?",
                    (f"{launch.job_id}:job_created", launch.job_id),
                ).fetchone()
                assert row is not None
                outbox = json.loads(str(row[1]))
                if tamper == "outbox_missing":
                    outbox.pop("execution_intent_binding", None)
                else:
                    outbox["execution_intent_binding"]["intent_band"] = "candidate_only"
                connection.execute(
                    "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
                    (json.dumps(outbox, sort_keys=True), row[0]),
                )
            elif tamper == "capability_actor_mismatched":
                original_load = service._load_payload_ref  # noqa: SLF001

                def load_foreign_manifest(payload_ref: str) -> dict[str, object]:
                    value = original_load(payload_ref)
                    if payload_ref == record.capability_manifest_ref:
                        actor = value.get("actor")
                        assert isinstance(actor, dict)
                        actor["tenant_id"] = "tenant-foreign"
                    return value

                monkeypatch.setattr(service, "_load_payload_ref", load_foreign_manifest)
            else:
                original_load = service._load_payload_ref  # noqa: SLF001

                def load_tampered_payload(payload_ref: str) -> dict[str, object]:
                    value = original_load(payload_ref)
                    if payload_ref == record.payload_ref:
                        if tamper == "payload_authorization_receipt_missing":
                            value.pop("nl_authorization_receipt", None)
                        else:
                            receipt = value.get("nl_authorization_receipt")
                            assert isinstance(receipt, dict)
                            snapshot = receipt.get("permission_snapshot")
                            assert isinstance(snapshot, dict)
                            snapshot["subject"] = "user-foreign"
                    return value

                monkeypatch.setattr(service, "_load_payload_ref", load_tampered_payload)
            connection.commit()

        reached: list[str] = []

        def forbidden_eval_safety(**_kwargs: object) -> object:
            reached.append("evaluation_safety")
            raise RuntimeError("protected_intent_reached_evaluation_safety_without_binding")

        async def forbidden_compiler(**_kwargs: object) -> object:
            reached.append("n4")
            raise RuntimeError("protected_intent_reached_n4_without_binding")

        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", forbidden_compiler)
        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        blocked = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert blocked is not None
        assert blocked.state == "failed"
        expected_error = (
            "control_job_created_event_outbox_mismatch"
            if tamper.startswith(("event_", "outbox_"))
            else (
                "control_job_capability_manifest_actor_mismatch"
                if tamper == "capability_actor_mismatched"
                else "nl_job_execution_intent_not_established"
            )
        )
        assert blocked.error_message == expected_error
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context", "expected_band"),
    [
        ({"evaluation_safety_attempt": {"requested_mode_token": "field_pilot "}}, "not_established"),
        ({"evaluation_safety_attempt": {"requested_mode_token": "field_pilot"}}, "eval_safety_required"),
    ],
)
async def test_unestablished_attempt_band_refuses_before_evaluation_safety_or_n4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    context: dict[str, object],
    expected_band: str,
    ) -> None:
    service = _build_control_service(tmp_path)
    try:
        request = NaturalLanguageRunRequest(
            request="Keep an incomplete protected intent from becoming a candidate run.",
            llm_model="simulated-qwen",
            context=context,
        )
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        payload = service._load_payload_ref(str(record.payload_ref))  # noqa: SLF001
        binding = payload.get("execution_intent_binding")
        assert isinstance(binding, dict)
        assert binding.get("intent_band") == expected_band
        assert binding.get("admission_status") == "not_established"

        status = service.get_job_status(launch.job_id)
        assert record.state == status.state == "failed"
        assert record.finished_at is not None
        assert record.lease_owner is None
        assert record.progress["state"] == status.progress["state"] == "failed"
        assert status.progress["failure_code"] == "nl_job_execution_intent_not_established"
        assert service._control_store.get_job_created_event_payload(  # noqa: SLF001
            launch.job_id
        )["state"] == "failed"
        assert _outbox_payload(service, launch.job_id)["state"] == "failed"
        assert service._control_store.list_job_state_transitions(launch.job_id) == [  # noqa: SLF001
            "failed"
        ]
        admission_transitions = [
            item.event
            for item in service._control_store.list_diagnostic_events(  # noqa: SLF001
                job_id=launch.job_id
            )
            if item.event.event_type == "polisyos.runtime.diagnostic.phase_transition.v1"
        ]
        assert len(admission_transitions) == 1
        assert admission_transitions[0].state_after == "failed"
        assert service._control_store.lease_next_job(  # noqa: SLF001
            worker_id="r5-unestablished-intent-probe"
        ) is None

        reached: list[str] = []

        def forbidden_eval_safety(**_kwargs: object) -> object:
            reached.append("evaluation_safety")
            raise RuntimeError("unestablished_intent_reached_evaluation_safety")

        async def forbidden_compiler(**_kwargs: object) -> object:
            reached.append("n4")
            raise RuntimeError("unestablished_intent_reached_n4")

        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", forbidden_compiler)
        from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError

        with pytest.raises(ControlJobLeaseLostError):
            service._process_control_job(record)  # noqa: SLF001

        failed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert failed is not None
        assert failed.state == "failed"
        assert failed.error_message == "nl_job_execution_intent_not_established"
        assert reached == []
    finally:
        service.close()


@pytest.mark.asyncio
async def test_data_trust_band_keeps_candidate_compute_and_persists_bridge_limitation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationOrganRun,
        GenerationDiversityReport,
        GenerationUnderAResult,
        ModelProfilePreflight,
    )
    from polisyos.runtime.quality.generation_cycle import gy_content_hash
    from tests.unit.runtime.quality.test_generation_cycle import _problem

    problem = _problem("r5_data_trust_dispatch")
    terminal_generation = GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        model_id="simulated-qwen",
        preflight=ModelProfilePreflight(
            status="gateway_unavailable",
            model_id="simulated-qwen",
            supported_model_ids=("simulated-qwen",),
            reason="test_terminal",
        ),
        diversity_report=GenerationDiversityReport(
            min_required=1,
            candidate_count=0,
            unique_diversity_key_count=0,
        ),
    )
    compiler_result = N4CandidateProposalExecution(
        design_problem=problem,
        proposal=DesignGenerationOrganRun(result=terminal_generation),
    )
    request = NaturalLanguageRunRequest(
        request="Explore a retrospective policy option as a candidate.",
        llm_model="simulated-qwen",
        context={
            "evaluation_safety_attempt": _valid_intake_for_mode(
                "retrospective"
            ).model_dump(mode="json"),
            "data_trust_admission": {
                "status": "verified",
                "tenant_id": "tenant-foreign",
            },
        },
    )
    service = _build_control_service(tmp_path)
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(_fixture_claims(), request),
        )
        record = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert record is not None
        compiler_intents: list[object] = []

        async def candidate_compiler(**kwargs: object) -> object:
            compiler_intents.append(kwargs.get("execution_intent"))
            assert kwargs.get("root_evaluation_context") is None
            return compiler_result

        def forbidden_eval_safety(**_kwargs: object) -> object:
            pytest.fail("DataTrust intent was substituted into the EvalSafety owner")

        def forbidden_authority_consumer(**_kwargs: object) -> object:
            pytest.fail("DataTrust bridge absence reached an authority consumer")

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", candidate_compiler)
        monkeypatch.setattr(service, "_admit_evaluation_safety_attempt", forbidden_eval_safety)
        monkeypatch.setattr(service, "resolve_generation_value_choices", forbidden_authority_consumer)
        monkeypatch.setattr(service, "_publish_generation_run", forbidden_authority_consumer)

        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None
        assert completed.state == "completed"
        assert compiler_intents == ["candidate_only"]
        assert completed.progress["status"] == "not_established"
        assert completed.progress["execution_band"] == "candidate"
        assert completed.progress["execution_intent_band"] == "data_trust_required"
        assert completed.progress["execution_intent_limitation_code"] == (
            "data_trust_owner_not_established"
        )
        assert completed.progress["n4_status"] == "generation_unavailable"
        assert completed.progress["n5_status"] == "not_run"
        assert completed.progress["n8_status"] == "not_run"
        assert completed.progress["n9_status"] == "not_run"
        assert completed.progress["s8_status"] == "not_run"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_served_worker_persists_computation_without_s8_or_publication(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist real N4 output with an unavailable simulation, not a fake run."""
    import polisyos.runtime.http.services.control.generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalSimulationRecord,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _design_problem_tool_args,
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
        _intent_context,
    )
    from tests.unit.runtime.quality.test_design_generation import (
        RecordedClientWithCatalog,
        _recording_with_successful_first_response,
    )

    recording = _recording_with_successful_first_response()
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=_design_problem_tool_args(),
    )
    generation_gateway = RecordedClientWithCatalog(recording, model_ids=[model_id])
    original_compiler = nl_pipeline.build_design_problem_from_nl_request

    async def run_real_compiler(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        nl_pipeline,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        __import__("polisyos.scientist.orchestration.llm.factory", fromlist=["factory"]),
        "create_traced_gateway_client",
        lambda **_kwargs: generation_gateway,
    )

    service = _build_control_service(tmp_path)
    context = _intent_context(as_of="2026-05-15")
    context["evaluation_safety_attempt"] = _valid_intake_for_mode(
        "simulate_only"
    ).model_dump(mode="json")
    request = NaturalLanguageRunRequest(
        request="Design a wartime MSME credit guarantee for Ukraine within the stated "
        "UAH 10b budget cap. Simulate this candidate while carrying unknown "
        "world scope.",
        llm_model=model_id,
        context=context,
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(
                _fixture_claims(), request
            ),
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None and job.run_id is not None

        compiler_calls: list[tuple[object, object, object]] = []
        original_compile = service.compile_and_run_recursive_generation_cycle

        async def record_compiler_route(**kwargs):
            compiler_calls.append(
                (
                    kwargs["execution_intent"],
                    kwargs["n4_proposal_only"],
                    kwargs["root_evaluation_context"],
                )
            )
            return await original_compile(**kwargs)

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            record_compiler_route,
        )

        # Removal probe: removing the served selector leaves persisted markers
        # intact but sends simulate_only into generic N6, which this guard rejects.
        def forbidden_recursive_controller(**_kwargs: object) -> object:
            pytest.fail("no-context simulate_only entered N6 instead of stopping after N4")

        monkeypatch.setattr(
            generation_cycle_service,
            "build_default_recursive_generation_cycle_controller",
            forbidden_recursive_controller,
        )
        monkeypatch.setattr(
            service,
            "resolve_generation_value_choices",
            lambda **_kwargs: pytest.fail("simulate_only reached normative S8"),
        )
        monkeypatch.setattr(
            service,
            "_publish_generation_run",
            lambda **_kwargs: pytest.fail("simulate_only published a recursive run"),
        )

        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None and completed.state == "completed"
        progress = completed.progress
        assert compiler_calls == [("simulate_only", True, None)]
        assert progress["execution_intent_band"] == "simulate_only_attempt"
        assert progress["candidate_computation_status"] == "completed"
        assert progress["simulation_status"] == "simulation_unavailable"
        assert progress["simulation_limitation_code"] == (
            "cycle_substrate_context_not_established"
        )
        assert {
            progress["n5_status"],
            progress["n8_status"],
            progress["n9_status"],
            progress["s8_status"],
        } == {"not_run"}
        assert "publication_status" not in progress
        assert "compiled_recursive_generation_cycle_ref" not in progress
        assert "normative_disposition_ref" not in progress
        assert "manifest_ref" not in progress
        assert progress["candidate_proposal_ref"]

        repository = GenerationSourceRepository(service._artifact_store)
        proposal = repository.load_candidate_proposal_for_served_job(
            progress["candidate_proposal_ref"],
            job_id=launch.job_id,
            run_id=str(job.run_id),
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            raw_request=request.request,
        )
        assert isinstance(proposal, N4CandidateProposalSimulationRecord)
        assert proposal.proposal.trinity_bundle.policy_spec.interventions
        assert proposal.simulation_disposition.execution_intent_band == (
            "simulate_only_attempt"
        )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_n4_selector_refuses_an_owner_bound_cycle_context(
    tmp_path,
) -> None:
    """An admitted cycle context cannot be silently reduced to an N4 proposal."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        compile_and_run_recursive_generation_cycle,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        revalidate_cycle_substrate_context,
    )
    from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _cyc01_owner_bound_n5_case,
    )

    problem, substrate_context, _candidate = _cyc01_owner_bound_n5_case()
    revalidate_cycle_substrate_context(substrate_context)
    service = _build_control_service(tmp_path)
    try:
        with pytest.raises(DesignProblemAuthorityError) as exc_info:
            await compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="fixture-model",
                execution_intent="simulate_only",
                n4_proposal_only=True,
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=_budget(),
                recursive_budget=RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                root_evaluation_context=None,
                eval_safety_verifier=service._evaluation_safety_admission_verifier,  # noqa: SLF001
                cycle_substrate_context=substrate_context,
                promotion_runtime=service._promotion_runtime,  # noqa: SLF001
            )
        assert exc_info.value.code == "n4_proposal_only_context_conflict"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_simulate_only_n4_terminal_failure_is_not_simulation_unavailable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal N4 failure stays distinct from a persisted proposal outcome."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        N4CandidateProposalExecution,
    )
    from polisyos.runtime.quality import design_generation as n4
    from tests.unit.runtime.quality.test_design_generation import (
        _bundle,
        _test_design_problem,
    )

    service = _build_control_service(tmp_path)
    problem = _test_design_problem()
    result = n4.GenerationUnderAResult(
        status="generation_unavailable",
        design_problem_ref=n4.gy_content_hash(problem.model_dump(mode="json")),
        model_id="synthetic-c2",
        preflight=n4.ModelProfilePreflight(
            status="gateway_unavailable",
            model_id="synthetic-c2",
        ),
        diversity_report=n4.GenerationDiversityReport(
            min_required=1,
            candidate_count=0,
            unique_diversity_key_count=0,
        ),
    )
    terminal_n4 = result.as_organ_run(trinity_bundle=_bundle([]))
    compiled = N4CandidateProposalExecution(
        design_problem=problem,
        proposal=terminal_n4,
    )
    request = NaturalLanguageRunRequest(
        request="Simulate candidate options with unavailable N4 generation.",
        llm_model="simulated-qwen",
        context={
            "evaluation_safety_attempt": _valid_intake_for_mode(
                "simulate_only"
            ).model_dump(mode="json")
        },
    )
    try:
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
            authorization_proof=bound_nl_authorization_proof(
                _fixture_claims(), request
            ),
        )
        job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert job is not None

        async def terminal_n4_compiler(**_kwargs: object) -> object:
            return compiled

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            terminal_n4_compiler,
        )
        dispatch_one_control_job(
                    store=service._control_store,  # noqa: SLF001
                    handler=service._process_control_job,  # noqa: SLF001
                    expected_job_id=launch.job_id,
                )

        completed = service._control_store.get_job(launch.job_id)  # noqa: SLF001
        assert completed is not None and completed.state == "completed"
        assert completed.progress["n4_status"] == "generation_unavailable"
        assert completed.progress["simulation_status"] == "not_run"
        assert completed.progress["simulation_limitation_code"] == (
            "n4_generation_unavailable"
        )
        assert completed.progress["candidate_proposal_ref"] is None
        assert completed.progress["n5_status"] == completed.progress["s8_status"] == "not_run"
    finally:
        service.close()


@pytest.mark.asyncio
async def test_authenticated_launch_binds_all_five_intent_bands_and_actor_scope(tmp_path) -> None:
    service = _build_control_service(tmp_path)
    assert isinstance(service._control_store, GuardedDependencyProxy)  # noqa: SLF001
    cases = (
        ("candidate", {}, "candidate_only", "established", None),
        (
            "simulation",
            {"evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(mode="json")},
            "simulate_only_attempt",
            "established",
            "simulate_only",
        ),
        (
            "data_trust",
            {"evaluation_safety_attempt": _valid_intake_for_mode("retrospective").model_dump(mode="json")},
            "data_trust_required",
            "established",
            "retrospective",
        ),
        (
            "eval_safety",
            {"evaluation_safety_attempt": _valid_intake_for_mode("field_pilot").model_dump(mode="json")},
            "eval_safety_required",
            "established",
            "field_pilot",
        ),
        (
            "invalid_mode",
            {"evaluation_safety_attempt": {"requested_mode_token": "field_pilot "}},
            "not_established",
            "not_established",
            None,
        ),
        (
            "malformed_protected_attempt",
            {"evaluation_safety_attempt": {"requested_mode_token": "field_pilot"}},
            "eval_safety_required",
            "not_established",
            "field_pilot",
        ),
    )
    try:
        for name, context, expected_band, expected_status, expected_mode in cases:
            request = NaturalLanguageRunRequest(
                request=f"Run the {name} intent as a candidate or protected action.",
                llm_model="simulated-qwen",
                context=context,
            )
            launch = await service.launch_nl_run(
                request,
                principal=RuntimePrincipal.from_user_claims(_fixture_claims()),
                authorization_proof=bound_nl_authorization_proof(
                    _fixture_claims(), request
                ),
            )
            job = service._control_store.get_job(launch.job_id)  # noqa: SLF001
            assert job is not None
            assert job.submitted_by == "user-fixture"
            payload = service._load_payload_ref(str(job.payload_ref))  # noqa: SLF001
            binding = payload.get("execution_intent_binding")
            assert isinstance(binding, dict)
            assert binding.get("intent_band") == expected_band
            assert binding.get("admission_status") == expected_status
            assert binding.get("canonical_mode") == expected_mode
            assert binding.get("schema_version") == (
                "polisyos.runtime.control_execution_intent.v2"
            )
            assert binding.get("route_action") == "control.launch_nl_run"
            assert binding.get("actor_subject") == "user-fixture"
            assert binding.get("actor_authenticated") is True
            assert binding.get("tenant_id") == "tenant-fixture"
            assert binding.get("cell_id") == "cell-fixture"
            assert binding.get("job_id") == job.job_id
            assert binding.get("run_id") == job.run_id
            assert isinstance(binding.get("intent_digest"), str)

            _, created_event = _job_created_event(service, launch.job_id)
            outbox = _outbox_payload(service, launch.job_id)
            capability_manifest = service._load_payload_ref(  # noqa: SLF001
                str(job.capability_manifest_ref)
            )
            assert created_event.get("execution_intent_binding") == binding
            assert outbox.get("execution_intent_binding") == binding
            assert created_event.get("intent_digest") == binding.get("intent_digest")
            assert outbox.get("intent_digest") == binding.get("intent_digest")
            assert created_event.get("payload_ref") == job.payload_ref
            assert outbox.get("payload_ref") == job.payload_ref
            assert created_event.get("capability_manifest_ref") == job.capability_manifest_ref
            assert outbox.get("capability_manifest_ref") == job.capability_manifest_ref
            actor = capability_manifest.get("actor")
            assert isinstance(actor, dict)
            assert actor.get("subject") == binding.get("actor_subject")
            assert actor.get("authenticated") is binding.get("actor_authenticated")
            assert actor.get("tenant_id") == binding.get("tenant_id")
            assert actor.get("cell_id") == binding.get("cell_id")
    finally:
        service.close()


def test_control_job_creation_rolls_back_and_replays_through_guarded_store(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_control_service(tmp_path)
    store = service._control_store  # noqa: SLF001
    assert isinstance(store, GuardedDependencyProxy)
    raw_store = store._target  # noqa: SLF001
    job_id = "job-r5-transaction-replay"
    event_payload = {
        "job_id": job_id,
        "run_id": "run-r5-transaction-replay",
        "job_kind": "natural_language_run",
        "payload_ref": "sha256:" + "a" * 64,
        "execution_intent_binding": {"intent_band": "candidate_only"},
        "intent_digest": "sha256:" + "b" * 64,
        "capability_manifest_ref": "sha256:" + "c" * 64,
    }
    create_args = {
        "job_id": job_id,
        "kind": "natural_language_run",
        "run_id": "run-r5-transaction-replay",
        "pipeline_id": None,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {},
        "capability_manifest_ref": "sha256:" + "c" * 64,
        "payload_ref": "sha256:" + "a" * 64,
        "submitted_by": "user-fixture",
        "creation_event_payload": event_payload,
    }
    original_emit = raw_store._emit_job_outbox_event  # noqa: SLF001

    def append_then_interrupt(**kwargs: object) -> None:
        original_emit(**kwargs)
        raise RuntimeError("injected_after_outbox_insert")

    service_closed = False
    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(raw_store, "_emit_job_outbox_event", append_then_interrupt)
            with pytest.raises(RuntimeError, match="injected_after_outbox_insert"):
                store.create_job(**create_args)

        assert store.get_job(job_id) is None
        with raw_store._sqlite_connection() as connection:  # noqa: SLF001
            assert connection.execute(
                "SELECT count(*) FROM control_job_progress WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM control_job_events WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM control_outbox_events WHERE job_id = ?", (job_id,)
            ).fetchone()[0] == 0

        store.create_job(**create_args)
        service.close()
        service_closed = True
        reopened = _build_control_service(tmp_path)
        try:
            record = reopened._control_store.get_job(job_id)  # noqa: SLF001
            assert record is not None
            _, event = _job_created_event(reopened, job_id)
            outbox = _outbox_payload(reopened, job_id)
            assert outbox == event | {
                "effective_execution_profile": "dev",
                "pipeline_id": None,
            }
            assert event["execution_intent_binding"] == event_payload["execution_intent_binding"]
            assert outbox["intent_digest"] == event_payload["intent_digest"]
        finally:
            reopened.close()
    finally:
        if not service_closed:
            service.close()
