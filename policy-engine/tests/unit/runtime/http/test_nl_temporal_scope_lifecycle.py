"""Real selected NL queue, worker, cursor artifact, and projection witnesses.

The compiler seam deliberately terminates candidate work after actual admission
and cursor persistence. These witnesses prove requested intent, not data access,
legal admissibility, temporal currentness, or protected publication authority.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    EnvInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    WarningRecord,
    artifact_ref_identity_key,
    read_core_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.job_attempt_publication import _nl_request_body_bytes
from polisyos.runtime.http.services.control.job_scope_admission import _NL_JOB_OWNER_CONTEXT_KEYS
from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
from tests.unit.runtime.http.test_control_service_di import _fixture_claims

_SCOPE = {"valid_at": "2026-01-01T00:00:00Z", "tx_at": None, "scenario_id": "requested-scenario"}
_STOP = "temporal_fixture_stopped_after_real_cursor_bridge"


async def _launch(service, *, scope: object = ..., context: dict | None = None):
    values = {"request": "Record this requested cursor only.", "llm_model": "simulated-qwen"}
    if scope is not ...:
        values["temporal_scope"] = scope
    if context is not None:
        values["context"] = context
    request = NaturalLanguageRunRequest.model_validate(values)
    claims = _fixture_claims()
    launch = await service.launch_nl_run(
        request,
        principal=RuntimePrincipal.from_user_claims(claims),
        authorization_proof=bound_nl_authorization_proof(claims, request),
    )
    return request, launch


@contextmanager
def _admitted_job(service, job_id: str):
    """Use the real persisted lease/fence/scope rather than a constructed owner."""
    store = service._control_store
    lease = store.lease_next_job(worker_id="temporal-fixture-worker", lease_seconds=60)
    assert lease is not None and lease.job_id == job_id
    with store.job_execution_fence(
        job_id=job_id, worker_id=lease.lease_owner, attempt=lease.attempt
    ):
        admission = store.current_execution_job_admission()
        with service._install_execution_scope(admission.scope):
            created = store.get_job_created_event_payload(job_id)
            payload = service._load_control_nl_job_payload(admission.job)
            yield admission, created, payload


def _assert_temporal_bridge(response, compiler_inputs: dict[str, Any], expected_scope: dict):
    selected = response.runtime_quality_artifact_refs.get("time_context_ref")
    assert selected is not None, "selected cursor bridge missing"
    trusted = compiler_inputs.get("trusted_source_context")
    assert isinstance(trusted, dict), "trusted cursor bridge missing"
    assert trusted["temporal_scope"] == expected_scope
    assert trusted["temporal_scope_artifact_ref"] == selected.model_dump(mode="json")
    binding = response.progress["temporal_scope_request_binding"]
    assert trusted["temporal_scope_request_binding"] == binding
    assert binding["temporal_scope_ref"] == selected.model_dump(mode="json")
    assert binding["requested_view_only"] is True
    assert binding["limitation_code"] == "temporal_scope_consumed_view_not_established"
    assert compiler_inputs["execution_intent"] == "candidate_only"
    return selected, binding


@pytest.mark.asyncio
async def test_selected_job_created_queue_reopens_in_fresh_worker_and_projects_requested_intent(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _build_control_service(tmp_path)
    try:
        temporal_aliases = {
            "temporal_scope",
            "temporal_scope_artifact_ref",
            "temporal_scope_request_binding",
            "time_context_ref",
        }
        # Keep known aliases even if one is accidentally removed from the intake
        # owner set. The emitted trusted key set below independently bounds coverage.
        forged_owner_context = dict.fromkeys(
            _NL_JOB_OWNER_CONTEXT_KEYS | temporal_aliases, "caller-forged"
        )
        _, launch = await _launch(
            first,
            scope=_SCOPE,
            context={
                **forged_owner_context,
                "as_of": "1999-12-31",
                "policy_time": "2040-01-01",
            },
        )
        created = first._control_store.get_job_created_event_payload(launch.job_id)
        outbox = first._control_store.get_job_created_outbox_event(launch.job_id)
        assert outbox is not None
        queue_ref = ArtifactRef.model_validate(created["nl_request_payload_artifact_ref"])
        assert outbox.payload["nl_request_payload_artifact_ref"] == queue_ref.model_dump(
            mode="json"
        )
        assert queue_ref.manifest_profile_sha256
        initial_store = first._artifact_store
    finally:
        first.close()

    fresh = _build_control_service(tmp_path)
    compiler_inputs: dict[str, Any] = {}
    try:
        assert fresh._artifact_store is not initial_store

        async def stop_after_cursor(**kwargs):
            compiler_inputs.update(kwargs)
            raise RuntimeError(_STOP)

        monkeypatch.setattr(fresh, "compile_and_run_recursive_generation_cycle", stop_after_cursor)
        dispatch_one_control_job(
            store=fresh._control_store,
            handler=fresh._process_control_job,
            expected_job_id=launch.job_id,
        )
        response = fresh.get_job_status(launch.job_id)
        assert response.state == "failed" and response.error_message == _STOP
        scope_ref, binding = _assert_temporal_bridge(response, compiler_inputs, _SCOPE)
        assert binding["request_payload_ref"] == queue_ref.model_dump(mode="json")
        assert binding["job_id"] == launch.job_id and binding["run_id"] == launch.run_id
        assert binding["tenant_id"] == _fixture_claims().tenant_id
        assert binding["cell_id"] == _fixture_claims().cell_id
        candidate = compiler_inputs["context"]["candidate_context"]
        assert candidate["as_of"] == "1999-12-31"
        assert candidate["policy_time"] == "2040-01-01"
        emitted_owner_keys = set(compiler_inputs["trusted_source_context"])
        assert emitted_owner_keys <= set(forged_owner_context)
        for owner_key in set(forged_owner_context) | emitted_owner_keys:
            assert owner_key not in candidate
        assert binding != forged_owner_context["temporal_scope_request_binding"]

        manifest = fresh._artifact_store.get_manifest(scope_ref)
        assert manifest.artifact_schema == SchemaInfo(
            name="polisyos.runtime.TemporalScope", version="1.0"
        )
        assert manifest.authority is None
        assert manifest.same_input_closure.status == "candidate_only"
        assert manifest.producer.version == "1.0"
        assert manifest.inputs == [
            InputRef(
                artifact_id=queue_ref.artifact_id,
                manifest_profile_sha256=queue_ref.manifest_profile_sha256,
                role="authorized_nl_request_payload",
            )
        ]
        assert read_core_json_artifact(fresh._artifact_store, scope_ref).value == _SCOPE
        assert response.approval_projection.eligible is False
        assert response.authoritative_scorecard_ref is None
        events = fresh._control_store.list_outbox_events(state=None, limit=500)
        assert any(
            event.topic == "control.job.progress"
            and event.job_id == launch.job_id
            and event.payload.get("temporal_scope_request_binding") == binding
            for event in events
        )
    finally:
        fresh.close()

    reopened = _build_control_service(tmp_path)
    try:
        response = reopened.get_job_status(launch.job_id)
        assert response.runtime_quality_artifact_refs["time_context_ref"] == scope_ref
        assert response.progress["temporal_scope_request_binding"] == binding
        assert read_core_json_artifact(reopened._artifact_store, scope_ref).value == _SCOPE
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_selected_queue_uses_admitted_profile_and_refuses_missing_unknown_or_wrong_view(
    tmp_path,
) -> None:
    from polisyos.runtime.http.services.control.temporal_scope import read_nl_job_payload

    service = _build_control_service(tmp_path)
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        record = service._control_store.get_job(launch.job_id)
        created = service._control_store.get_job_created_event_payload(launch.job_id)
        selected = ArtifactRef.model_validate(created["nl_request_payload_artifact_ref"])
        fresh_store = FileSystemCAS(tmp_path / ".polisyos")
        original = read_nl_job_payload(
            store=fresh_store, job=record, created=created, legacy_reader=service._load_payload_ref
        )
        missing = dict(created)
        missing.pop("nl_request_payload_artifact_ref")
        with pytest.raises(ValueError, match="selected_queue_not_established"):
            read_nl_job_payload(
                store=fresh_store,
                job=record,
                created=missing,
                legacy_reader=service._load_payload_ref,
            )
        wrong_profile = fresh_store.put_json(
            original,
            ArtifactWriteOptions(
                kind=selected.kind,
                media_type=selected.media_type,
                schema=SchemaInfo(name="tests.WrongQueueSchema", version="1.1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert str(wrong_profile.artifact_id) == str(selected.artifact_id)
        assert wrong_profile.manifest_profile_sha256 != selected.manifest_profile_sha256
        assert (
            read_nl_job_payload(
                store=fresh_store,
                job=record,
                created=created,
                legacy_reader=service._load_payload_ref,
            )
            == original
        )
        assert original["temporal_scope"] == _SCOPE
        for bad_ref, expected_error in (
            (wrong_profile, "selected_queue_schema_mismatch"),
            (
                selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64}),
                "selected_queue_integrity_failed",
            ),
            (selected.model_copy(update={"kind": "tests.wrong_kind"}), "selected_ref_invalid"),
            (selected.model_copy(update={"manifest_profile_sha256": None}), "selected_ref_invalid"),
        ):
            changed = {
                **created,
                "nl_request_payload_artifact_ref": bad_ref.model_dump(mode="json"),
            }
            with pytest.raises(ValueError, match=expected_error):
                read_nl_job_payload(
                    store=fresh_store,
                    job=record,
                    created=changed,
                    legacy_reader=service._load_payload_ref,
                )
        with pytest.raises(ValueError, match="selected_queue_binding_mismatch"):
            read_nl_job_payload(
                store=fresh_store,
                job=replace(record, payload_ref="sha256:" + "1" * 64),
                created=created,
                legacy_reader=service._load_payload_ref,
            )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_mutable_worker_context_cannot_replace_the_selected_authorized_queue(
    tmp_path,
) -> None:
    from polisyos.runtime.http.services.control.temporal_scope import (
        materialize_temporal_scope_for_job,
    )

    service = _build_control_service(tmp_path)
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        with _admitted_job(service, launch.job_id) as (admission, created, payload):
            before = service._artifact_store.manifest_inventory_snapshot(
                kind="runtime.temporal_scope"
            )
            assert before.verdict == "pass"
            changed = deepcopy(payload)
            changed["context"]["as_of"] = "caller-mutated-after-admission"
            with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
                materialize_temporal_scope_for_job(
                    store=service._artifact_store,
                    job=admission.job,
                    scope=admission.scope,
                    created=created,
                    payload=changed,
                )
            after = service._artifact_store.manifest_inventory_snapshot(
                kind="runtime.temporal_scope"
            )
            assert after.verdict == "pass" and after.entries == before.entries
    finally:
        service.close()


@pytest.mark.asyncio
async def test_unlinked_cursor_write_replays_same_selected_intent_without_claiming_consumption(
    tmp_path,
) -> None:
    from polisyos.runtime.http.services.control.temporal_scope import (
        TemporalScopeRequestBinding,
        materialize_temporal_scope_for_job,
        resolve_temporal_scope_for_job,
    )

    service = _build_control_service(tmp_path)
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        with _admitted_job(service, launch.job_id) as (admission, created, payload):
            kwargs = {
                "store": service._artifact_store,
                "job": admission.job,
                "scope": admission.scope,
                "created": created,
                "payload": payload,
            }
            first = materialize_temporal_scope_for_job(**kwargs)
            assert (
                "temporal_scope_request_binding"
                not in service._control_store.get_job(launch.job_id).progress
            )
            # Resume the owner with no durable linkage: reissue the exact options,
            # not a new clock/default cursor. This is a CAS-to-linkage component witness.
            second = materialize_temporal_scope_for_job(**kwargs)
            assert artifact_ref_identity_key(first.temporal_scope_ref) == artifact_ref_identity_key(
                second.temporal_scope_ref
            )
            third = materialize_temporal_scope_for_job(
                **kwargs, persisted_binding=second.model_dump(mode="json")
            )
            assert third == first
            assert resolve_temporal_scope_for_job(**kwargs, binding=third) == _SCOPE
            assert third.requested_view_only is True
            assert third.limitation_code == "temporal_scope_consumed_view_not_established"
            for forged in (
                {"requested_view_only": False},
                {"legal_authority": True},
                {"current_world_verified": True},
            ):
                with pytest.raises(ValidationError):
                    TemporalScopeRequestBinding.model_validate({**third.model_dump(), **forged})
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name", ["job_id", "run_id", "tenant_id", "cell_id", "request_content_hash"]
)
async def test_requested_cursor_binding_rejects_scope_and_request_substitution(
    tmp_path, field_name
) -> None:
    from polisyos.runtime.http.services.control.temporal_scope import (
        materialize_temporal_scope_for_job,
        resolve_temporal_scope_for_job,
    )

    service = _build_control_service(tmp_path)
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        with _admitted_job(service, launch.job_id) as (admission, created, payload):
            kwargs = {
                "store": service._artifact_store,
                "job": admission.job,
                "scope": admission.scope,
                "created": created,
                "payload": payload,
            }
            binding = materialize_temporal_scope_for_job(**kwargs)
            replacement = (
                "sha256:" + "0" * 64 if field_name == "request_content_hash" else "foreign"
            )
            with pytest.raises(ValueError, match="nl_temporal_scope_request_binding_mismatch"):
                resolve_temporal_scope_for_job(
                    **kwargs, binding=binding.model_copy(update={field_name: replacement})
                )
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["producer", "schema", "role", "env", "warnings"])
async def test_cursor_reader_reconstructs_complete_owner_profile_before_admitting_intent(
    tmp_path, mutation: str
) -> None:
    from polisyos.runtime.http.services.control.temporal_scope import (
        _scope_options,
        materialize_temporal_scope_for_job,
        resolve_temporal_scope_for_job,
    )

    service = _build_control_service(tmp_path)
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        with _admitted_job(service, launch.job_id) as (admission, created, payload):
            kwargs = {
                "store": service._artifact_store,
                "job": admission.job,
                "scope": admission.scope,
                "created": created,
                "payload": payload,
            }
            binding = materialize_temporal_scope_for_job(**kwargs)
            options = _scope_options(
                job=admission.job, scope=admission.scope, queue_ref=binding.request_payload_ref
            )
            replacements = {
                "producer": {
                    "producer": ProducerInfo(component="tests.unappointed.cursor", version="1.0")
                },
                "schema": {"schema": SchemaInfo(name="tests.WrongCursor", version="1.0")},
                "role": {
                    "inputs": [
                        InputRef(
                            artifact_id=binding.request_payload_ref.artifact_id,
                            manifest_profile_sha256=binding.request_payload_ref.manifest_profile_sha256,
                            role="different_role",
                        )
                    ]
                },
                "env": {"env": EnvInfo(python="test", platform="test", deps_lock_hash="test")},
                "warnings": {"warnings": [WarningRecord(code="injected", msg="changed profile")]},
            }
            bad_ref = service._artifact_store.put_json(
                _SCOPE,
                replace(options, **replacements[mutation]),
                canon_spec=CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=False),
                return_selected_profile=True,
            )
            assert str(bad_ref.artifact_id) == str(binding.temporal_scope_ref.artifact_id)
            assert (
                bad_ref.manifest_profile_sha256
                != binding.temporal_scope_ref.manifest_profile_sha256
            )
            forged = binding.model_copy(update={"temporal_scope_ref": bad_ref})
            with pytest.raises(ValueError, match="nl_temporal_scope_owner_profile_mismatch"):
                resolve_temporal_scope_for_job(**kwargs, binding=forged)
    finally:
        service.close()


@pytest.mark.asyncio
async def test_progress_updates_retain_cursor_binding_and_reject_conflicting_replacement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    compiler_inputs: dict[str, Any] = {}
    try:
        _, launch = await _launch(service, scope=_SCOPE)

        async def update_after_cursor(**kwargs):
            compiler_inputs.update(kwargs)
            current = service._control_store.current_execution_job_admission()
            binding = current.job.progress["temporal_scope_request_binding"]
            refs = current.job.progress["runtime_quality_artifact_refs"]
            service._control_store.update_progress_state(
                job_id=launch.job_id,
                state="running",
                progress={"state": "running", "phase": "later"},
            )
            retained = service._control_store.get_job(launch.job_id).progress
            assert retained["temporal_scope_request_binding"] == binding
            assert (
                retained["runtime_quality_artifact_refs"]["time_context_ref"]
                == refs["time_context_ref"]
            )
            changed_binding = {**binding, "request_content_hash": "sha256:" + "0" * 64}
            with pytest.raises(ControlJobLeaseLostError, match="progress_binding_conflict"):
                service._control_store.update_progress_state(
                    job_id=launch.job_id,
                    state="running",
                    progress={"temporal_scope_request_binding": changed_binding},
                )
            changed_ref = {
                **refs["time_context_ref"],
                "manifest_profile_sha256": "sha256:" + "0" * 64,
            }
            with pytest.raises(ControlJobLeaseLostError, match="progress_ref_conflict"):
                service._control_store.update_progress_state(
                    job_id=launch.job_id,
                    state="running",
                    progress={"runtime_quality_artifact_refs": {"time_context_ref": changed_ref}},
                )
            raise RuntimeError(_STOP)

        monkeypatch.setattr(
            service, "compile_and_run_recursive_generation_cycle", update_after_cursor
        )
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        response = service.get_job_status(launch.job_id)
        assert response.error_message == _STOP
        _assert_temporal_bridge(response, compiler_inputs, _SCOPE)
    finally:
        service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("null_in_body", [False, True])
async def test_raw_body_and_typed_cursor_must_agree_on_explicit_null_presence(
    tmp_path, null_in_body: bool
) -> None:
    service = _build_control_service(tmp_path)
    claims = _fixture_claims()
    body_scope = {"snapshot_id": "s-1", **({"tx_at": None} if null_in_body else {})}
    typed_scope = {"snapshot_id": "s-1", **({} if null_in_body else {"tx_at": None})}
    body_request = NaturalLanguageRunRequest.model_validate(
        {"request": "presence", "llm_model": "simulated-qwen", "temporal_scope": body_scope}
    )
    typed_request = NaturalLanguageRunRequest.model_validate(
        {"request": "presence", "llm_model": "simulated-qwen", "temporal_scope": typed_scope}
    )
    try:
        with pytest.raises(ValueError, match="nl_route_authorization_request_body_mismatch"):
            await service.launch_nl_run(
                typed_request,
                principal=RuntimePrincipal.from_user_claims(claims),
                authorization_proof=bound_nl_authorization_proof(claims, body_request),
                authorization_request_body=_nl_request_body_bytes(body_request),
            )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_dto_to_queue_bridge_removal_is_detected_behaviorally(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    original_enqueue = service._enqueue_job

    def omit_cursor_at_queue_boundary(**kwargs):
        payload = dict(kwargs["payload"])
        payload.pop("temporal_scope")
        return original_enqueue(**{**kwargs, "payload": payload})

    monkeypatch.setattr(service, "_enqueue_job", omit_cursor_at_queue_boundary)
    try:
        with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
            await _launch(service, scope=_SCOPE)
    finally:
        service.close()


@pytest.mark.asyncio
async def test_queue_to_cursor_producer_removal_breaks_the_same_fresh_projection_oracle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    observed: dict[str, Any] = {}
    try:
        _, launch = await _launch(service, scope=_SCOPE)
        monkeypatch.setattr(service, "_prepare_control_nl_temporal_context", lambda _context: None)

        async def stop_without_cursor(**kwargs):
            observed.update(kwargs)
            raise RuntimeError(_STOP)

        monkeypatch.setattr(
            service, "compile_and_run_recursive_generation_cycle", stop_without_cursor
        )
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        response = service.get_job_status(launch.job_id)
        assert response.error_message == _STOP
        with pytest.raises(AssertionError, match="selected cursor bridge missing"):
            _assert_temporal_bridge(response, observed, _SCOPE)
    finally:
        service.close()


@pytest.mark.asyncio
async def test_mixed_legacy_worker_retains_unselected_request_and_no_temporal_artifact(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _build_control_service(tmp_path)
    observed: dict[str, Any] = {}
    try:
        _, launch = await _launch(service)
        created = service._control_store.get_job_created_event_payload(launch.job_id)
        assert "nl_request_payload_artifact_ref" not in created
        record = service._control_store.get_job(launch.job_id)
        payload = service._load_control_nl_job_payload(record)
        assert "temporal_scope" not in payload
        assert (
            payload["nl_request_snapshot"]["schema_version"]
            == "polisyos.runtime.control_nl_request_snapshot.v1"
        )

        async def legacy_compiler(**kwargs):
            observed.update(kwargs)
            raise RuntimeError(_STOP)

        monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", legacy_compiler)
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=launch.job_id,
        )
        response = service.get_job_status(launch.job_id)
        assert response.error_message == _STOP
        assert "temporal_scope_request_binding" not in response.progress
        assert "time_context_ref" not in response.runtime_quality_artifact_refs
        assert "temporal_scope" not in observed["trusted_source_context"]
    finally:
        service.close()
