from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionOwnerExecutionResult,
    AcquisitionRouteMutationRequest,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service
from tests.unit.runtime.quality.test_acquisition_route_loop import (
    _append_terminal,
    _compiled,
)


@dataclass
class _Port:
    service: AcquisitionActionService
    closure: object
    calls: list[str]
    owner_ref: str

    def execute(self, closure):
        assert closure == self.closure
        seed = self.service._phase_receipt(
            closure=closure,
            job_id="job-acquisition",
            decision_ref="sha256:" + "9" * 64,
            receipt_phase="requested",
            predecessor_receipt_ref=None,
            owner_receipt_refs=(),
        )
        head = self.service.control_service.acquisition_route_sink.get_head(seed)
        assert head is not None
        assert head.receipt_phase == "executing"
        self.calls.append("effect")
        return AcquisitionOwnerExecutionResult(
            disposition="quarantined_no_growth",
            owner_receipt_refs=(self.owner_ref,),
            admitted_observation_delta=0,
        )

    def reenter(self, closure, result):  # pragma: no cover - quarantine invariant
        del closure, result
        raise AssertionError("quarantine cannot re-enter")

    def resume_reentry(self, closure, owner_receipt_refs):  # pragma: no cover
        del closure, owner_receipt_refs
        raise AssertionError("quarantine cannot recover re-entry")


class _Gateway:
    def __init__(self, *, calls: list[str], effect_handler, decision_missing: bool) -> None:
        self._calls = calls
        self._effect_handler = effect_handler
        self._decision_missing = decision_missing

    def load_persisted_decision(self, decision_ref: str):
        self._calls.append("load-decision")
        assert decision_ref == "sha256:" + "9" * 64
        if self._decision_missing:
            raise RuntimeError("durable decision missing")
        return object()

    def execute_bound_effect(self, *, operation, invocation, intent, persisted):
        del operation, intent, persisted
        self._calls.append("execute-bound-effect")
        return self._effect_handler(invocation)


class _Provider:
    def __init__(self, *, calls: list[str], decision_missing: bool) -> None:
        self._calls = calls
        self._decision_missing = decision_missing

    def for_job(self, *, effect_handler, **_kwargs):
        return _Gateway(
            calls=self._calls,
            effect_handler=effect_handler,
            decision_missing=self._decision_missing,
        )

    def for_request(self, **_kwargs):  # pragma: no cover - worker-only harness
        raise AssertionError("worker cannot recreate HTTP authority")


async def _worker_harness(tmp_path: Path, *, decision_missing: bool):
    control = _build_control_service(tmp_path)
    compiled = await _compiled()
    compiled_ref = control._put_json_artifact(
        compiled.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
    )
    manifest_ref = control._put_json_artifact(
        {"capability": "ds15"},
        kind="runtime.capability_manifest",
        schema_name="CapabilityManifest",
    )
    source_payload_ref = control._put_json_artifact(
        {"tenant_id": "tenant-a", "cell_id": "cell-a", "run_id": "run-ds15"},
        kind="runtime.control_job_payload.natural_language_run",
        schema_name="polisyos.runtime.ControlJobPayload",
    )
    store = control._control_store
    store.create_job(
        job_id="job-natural-language",
        kind="natural_language_run",
        run_id="run-ds15",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=source_payload_ref,
        submitted_by="tester",
    )
    store.complete_job(
        job_id="job-natural-language",
        run_id="run-ds15",
        capability_manifest_ref=manifest_ref,
        progress={
            "state": "completed",
            "phase": "natural_language_run",
            "run_id": "run-ds15",
            "compiled_recursive_generation_cycle_ref": compiled_ref,
        },
    )
    _append_terminal(
        control._diagnostic_event_log,
        run_id="run-ds15",
        job_id="job-natural-language",
        compiled_ref=compiled_ref,
        manifest_ref=manifest_ref,
    )

    service = object.__new__(AcquisitionActionService)
    service.control_service = control
    service.human_decision_service = object()
    calls: list[str] = []
    service._authority_provider = _Provider(calls=calls, decision_missing=decision_missing)
    closure = service._resolve(tenant_id="tenant-a", cell_id="cell-a", run_id="run-ds15")
    owner_ref = control._put_json_artifact(
        {"disposition": "quarantined_no_growth"},
        kind="runtime_quality.acquisition_owner_receipt",
        schema_name="polisyos.runtime.AcquisitionOwnerReceipt",
    )
    service._execution_port = _Port(
        service=service,
        closure=closure,
        calls=calls,
        owner_ref=owner_ref,
    )
    control.bind_acquisition_job_handler(service.handle_job)
    projection = service._projection(closure)
    request = AcquisitionRouteMutationRequest(
        route_projection_hash=projection.route_projection_hash,
        planner_report_hash=projection.planner_report_hash,
        replay_pins=projection.replay_pins,
        idempotency_key="worker-order",
        human_decision_record_ref="sha256:" + "8" * 64,
    )
    operation, invocation, intent = service._action_tuple(closure, request)
    payload = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-ds15",
        "route_id": closure.route_id,
        "decision_ref": "sha256:" + "9" * 64,
        "request": request.model_dump(mode="json"),
        "operation": operation.model_dump(mode="json"),
        "invocation": invocation.model_dump(mode="json"),
        "intent": intent.model_dump(mode="json"),
    }
    payload_ref = control._put_json_artifact(
        payload,
        kind="runtime.control_job_payload.acquisition",
        schema_name="polisyos.runtime.ControlJobPayload",
    )
    store.create_job(
        job_id="job-acquisition",
        kind="acquisition",
        run_id="run-ds15",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=payload_ref,
        submitted_by="tester",
    )
    requested = service._phase_receipt(
        closure=closure,
        job_id="job-acquisition",
        decision_ref="sha256:" + "9" * 64,
        receipt_phase="requested",
        predecessor_receipt_ref=None,
        owner_receipt_refs=(),
    )
    control.acquisition_route_sink.persist_phase(requested)
    return control, service, calls, requested


@pytest.mark.asyncio
async def test_worker_missing_durable_decision_fails_before_owner_effect(tmp_path: Path) -> None:
    control, _service, calls, requested = await _worker_harness(
        tmp_path,
        decision_missing=True,
    )
    try:
        job = control._control_store.get_job("job-acquisition")
        assert job is not None

        control._process_control_job(job)

        failed = control._control_store.get_job("job-acquisition")
        assert failed is not None
        assert failed.state == "failed"
        assert calls == ["load-decision"]
        head = control.acquisition_route_sink.get_head(requested)
        assert head is not None
        assert head.receipt_phase == "executing"
    finally:
        control.close()


@pytest.mark.asyncio
async def test_worker_loads_durable_decision_before_sealed_effect_and_terminal(
    tmp_path: Path,
) -> None:
    control, _service, calls, requested = await _worker_harness(
        tmp_path,
        decision_missing=False,
    )
    try:
        job = control._control_store.get_job("job-acquisition")
        assert job is not None

        control._process_control_job(job)

        completed = control._control_store.get_job("job-acquisition")
        assert completed is not None
        assert completed.state == "completed"
        assert calls == ["load-decision", "execute-bound-effect", "effect"]
        head = control.acquisition_route_sink.get_head(requested)
        assert head is not None
        assert head.receipt_phase == "terminal"
        assert head.recovery_state == "complete"
    finally:
        control.close()
