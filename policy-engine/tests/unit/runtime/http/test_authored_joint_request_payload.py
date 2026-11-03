"""Selected queue replay binds authored candidate composition to real NL admission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.services.control.temporal_scope import (
    read_authored_joint_request_payload,
    read_nl_job_payload,
)
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
from tests.unit.runtime.http.test_control_service_di import _fixture_claims


async def _admit(service: Any, *, intent: str | None) -> tuple[Any, dict[str, Any]]:
    """Use the real durable intake rather than constructing authorization fields."""
    request = NaturalLanguageRunRequest(
        request="Simulate this explicitly authored candidate compound only.",
        llm_model="simulated-qwen",
        context={
            "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                mode="json"
            )
        },
        joint_interaction_candidate_intent=intent,
    )
    claims = _fixture_claims()
    launch = await service.launch_nl_run(
        request,
        principal=RuntimePrincipal.from_user_claims(claims),
        authorization_proof=bound_nl_authorization_proof(claims, request),
    )
    created = service._control_store.get_job_created_event_payload(launch.job_id)
    return launch, created


@pytest.mark.asyncio
async def test_authored_request_reopens_actual_selected_queue_and_refuses_scope_drift(
    tmp_path: Path,
) -> None:
    first = _build_control_service(tmp_path)
    try:
        launch, created = await _admit(first, intent="authored_joint_components.v1")
        selected = ArtifactRef.model_validate(created["nl_request_payload_artifact_ref"])
        job = first._control_store.get_job(launch.job_id)
        assert job is not None and str(selected.artifact_id) == job.payload_ref
        outbox = first._control_store.get_job_created_outbox_event(launch.job_id)
        assert outbox is not None
        assert outbox.payload["nl_request_payload_artifact_ref"] == selected.model_dump(mode="json")
        original = read_nl_job_payload(
            store=first._artifact_store,
            job=job,
            created=created,
            legacy_reader=first._load_payload_ref,
        )
        binding = original["execution_intent_binding"]
        kwargs = {
            "request_payload_ref": selected,
            "expected_job_id": launch.job_id,
            "expected_run_id": launch.run_id,
            "expected_tenant_id": binding["tenant_id"],
            "expected_cell_id": binding["cell_id"],
            "expected_intent_digest": binding["intent_digest"],
        }
    finally:
        first.close()

    fresh = _build_control_service(tmp_path)
    try:
        assert fresh._artifact_store is not first._artifact_store
        assert (
            read_authored_joint_request_payload(store=fresh._artifact_store, **kwargs) == original
        )
        for key in (
            "expected_job_id",
            "expected_run_id",
            "expected_tenant_id",
            "expected_cell_id",
            "expected_intent_digest",
        ):
            with pytest.raises(ValueError, match="authored_joint_request_intent_binding_mismatch"):
                read_authored_joint_request_payload(
                    store=fresh._artifact_store, **{**kwargs, key: "foreign-value"}
                )
        # The exact old blob cannot silently select a mutable/default manifest.
        for ref in (
            selected.model_copy(update={"manifest_profile_sha256": None}),
            selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64}),
        ):
            with pytest.raises((OSError, RuntimeError, ValueError)):
                read_authored_joint_request_payload(
                    store=fresh._artifact_store, **{**kwargs, "request_payload_ref": ref}
                )
        # Same payload bytes, valid selected manifest, wrong semantic schema.
        wrong_view = fresh._artifact_store.put_json(
            original,
            ArtifactWriteOptions(
                kind=selected.kind,
                media_type=selected.media_type,
                schema=SchemaInfo(name="tests.OtherQueueSchema", version="1.1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert wrong_view.artifact_id == selected.artifact_id
        assert wrong_view.manifest_profile_sha256 != selected.manifest_profile_sha256
        with pytest.raises(ValueError, match="selected_queue_schema_mismatch"):
            read_authored_joint_request_payload(
                store=fresh._artifact_store, **{**kwargs, "request_payload_ref": wrong_view}
            )
        assert (
            read_authored_joint_request_payload(store=fresh._artifact_store, **kwargs) == original
        )
        # Historical default-only rows never establish this new authored intent.
        legacy_created = {
            key: value for key, value in created.items() if key != "nl_request_payload_artifact_ref"
        }
        with pytest.raises(ValueError, match="selected_queue_not_established"):
            read_nl_job_payload(
                store=fresh._artifact_store,
                job=job,
                created=legacy_created,
                legacy_reader=fresh._load_payload_ref,
            )
    finally:
        fresh.close()


@pytest.mark.asyncio
async def test_an_independently_admitted_ordinary_request_cannot_author_a_joint_relation(
    tmp_path: Path,
) -> None:
    service = _build_control_service(tmp_path)
    try:
        launch, created = await _admit(service, intent=None)
        job = service._control_store.get_job(launch.job_id)
        assert job is not None
        payload = service._load_payload_ref(
            job.payload_ref, kind="runtime.control_job_payload.natural_language_run"
        )
        binding = payload["execution_intent_binding"]
        selected = service._artifact_store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="runtime.control_job_payload.natural_language_run",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.runtime.ControlJobPayload", version="1.1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert "nl_request_payload_artifact_ref" not in created
        with pytest.raises(ValueError, match="authored_joint_request_intent_binding_mismatch"):
            read_authored_joint_request_payload(
                store=service._artifact_store,
                request_payload_ref=selected,
                expected_job_id=launch.job_id,
                expected_run_id=launch.run_id,
                expected_tenant_id=binding["tenant_id"],
                expected_cell_id=binding["cell_id"],
                expected_intent_digest=binding["intent_digest"],
            )
    finally:
        service.close()


@pytest.mark.asyncio
async def test_worker_uses_creation_selected_ref_and_stops_when_that_ref_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the actual queue/worker bridge, stopping before any compilation."""
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    service = _build_control_service(tmp_path)
    service.bind_llm_producer_settlement_store(
        BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "producer-ledger.json"))
    )
    compiler_inputs: list[dict[str, Any]] = []
    stop = "authored_request_fixture_stopped_after_real_worker_bridge"

    async def stop_after_bridge(**kwargs: Any) -> None:
        compiler_inputs.append(kwargs)
        raise RuntimeError(stop)

    monkeypatch.setattr(service, "compile_and_run_recursive_generation_cycle", stop_after_bridge)
    try:
        launch, created = await _admit(service, intent="authored_joint_components.v1")
        selected = ArtifactRef.model_validate(created["nl_request_payload_artifact_ref"])
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=launch.job_id,
            )
            == launch.job_id
        )
        status = service.get_job_status(launch.job_id)
        assert status.state == "failed" and status.error_message == stop
        assert len(compiler_inputs) == 1
        assert (
            compiler_inputs[0]["joint_interaction_candidate_intent"]
            == "authored_joint_components.v1"
        )
        assert compiler_inputs[0]["joint_interaction_request_payload_ref"] == selected
        assert compiler_inputs[0]["execution_intent"] == "simulate_only"

        second, _ = await _admit(service, intent="authored_joint_components.v1")
        original_created_reader = service._control_store.get_job_created_event_payload

        def without_selected_queue(job_id: str) -> dict[str, Any]:
            value = original_created_reader(job_id)
            if job_id == second.job_id:
                value = {
                    key: field
                    for key, field in value.items()
                    if key != "nl_request_payload_artifact_ref"
                }
            return value

        monkeypatch.setattr(
            service._control_store, "get_job_created_event_payload", without_selected_queue
        )
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=second.job_id,
            )
            == second.job_id
        )
        refused = service.get_job_status(second.job_id)
        assert refused.state == "failed"
        assert "selected_queue_not_established" in str(refused.error_message)
        assert len(compiler_inputs) == 1
    finally:
        service.close()
