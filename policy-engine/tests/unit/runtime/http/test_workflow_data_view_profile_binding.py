from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts import WorkflowDataSourceBinding as PublicWorkflowDataSourceBinding
from polisyos.core.contracts.control import (
    DataSourceBinding,
    WorkflowDataSourceBinding,
    WorkflowRunRequest,
)
from polisyos.core.contracts.fabric import DataViewRequestRef
from polisyos.core.contracts.foundry import FoundryInputBindingsRef
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.runtime.http.services._control_contracts import (
    _resolve_data_source,
    _resolve_workflow_data_source,
)
from polisyos.runtime.http.services.debug import _workflow_data_view_request_profile_origin

_SHA_A = "sha256:" + "a" * 64
_SHA_B = "sha256:" + "b" * 64


def _profiled_request(store: FileSystemCAS, version: str) -> DataViewRequestRef:
    body = DataViewRequest(
        schema_version="1.0",
        request_id="profile-origin-fixture",
        view_type="table",
        metrics=["fixture.dataset"],
    )
    ref = store.put_json(
        body,
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
            producer=ProducerInfo(
                component="polisyos.fabric.default_fabric_port",
                version=version,
            ),
        ),
    )
    return DataViewRequestRef.model_validate(
        {
            **ref.model_dump(mode="python"),
            "manifest_profile_sha256": artifact_manifest_profile_sha256(store.get_manifest(ref)),
        }
    )


def test_workflow_source_preserves_typed_profile_and_marks_legacy_as_default_limited() -> None:
    selected = DataViewRequestRef(
        artifact_id=_SHA_A,
        kind="ir.data_view_request",
        media_type="application/json",
        manifest_profile_sha256=_SHA_B,
    )
    assert PublicWorkflowDataSourceBinding is WorkflowDataSourceBinding
    key, ref, intent = _resolve_workflow_data_source(
        WorkflowDataSourceBinding(data_view_request_ref=selected)
    )
    assert key == "data_view_request_ref"
    assert ref is not None and intent is not None
    assert ref.model_dump(mode="json") == selected.model_dump(mode="json")
    assert intent.profile_origin == "caller_selected"

    key, legacy_ref, legacy_intent = _resolve_workflow_data_source(
        WorkflowDataSourceBinding(data_view_request_ref=_SHA_A)
    )
    assert key == "data_view_request_ref"
    assert legacy_ref.kind == "ir.data_view_request"
    assert legacy_ref.manifest_profile_sha256 is None
    assert legacy_intent.profile_origin == "worker_default"


def test_workflow_source_preserves_selected_foundry_binding_profile() -> None:
    """A selected input binding must retain its exact source carrier edge."""
    selected = FoundryInputBindingsRef(
        artifact_id=_SHA_A,
        kind="foundry.input_bindings",
        media_type="application/json",
        manifest_profile_sha256=_SHA_B,
    )
    key, ref, intent = _resolve_workflow_data_source(
        WorkflowDataSourceBinding.model_validate(
            {"input_bindings_ref": selected.model_dump(mode="json")}
        )
    )
    assert key == "input_bindings_ref"
    assert ref.model_dump(mode="json") == selected.model_dump(mode="json")
    assert intent is None
    nl_key, nl_ref = _resolve_data_source(DataSourceBinding(input_bindings_ref=selected))
    assert nl_key == "input_bindings_ref" and nl_ref == selected

    legacy_key, legacy_ref, _ = _resolve_workflow_data_source(
        WorkflowDataSourceBinding(input_bindings_ref=_SHA_A)
    )
    assert legacy_key == "input_bindings_ref"
    assert legacy_ref.manifest_profile_sha256 is None
    assert "registered_sql_admission_ref" not in WorkflowDataSourceBinding(
        input_bindings_ref=_SHA_A
    ).model_dump(mode="json")


def test_selected_foundry_profile_survives_real_job_creation(runtime_api_env) -> None:
    """The real job payload and creation records retain the complete selector."""
    service = runtime_api_env["app"].state._control_service
    selected = FoundryInputBindingsRef(
        artifact_id=_SHA_A,
        kind="foundry.input_bindings",
        media_type="application/json",
        manifest_profile_sha256=_SHA_B,
    )
    launched = service.launch_workflow_run(
        WorkflowRunRequest(data_source=WorkflowDataSourceBinding(input_bindings_ref=selected))
    )
    job = service._control_store.get_job(launched.job_id)
    assert job is not None
    event = service._control_store.get_job_created_event_payload(job.job_id)
    outbox = service._control_store.get_job_created_outbox_event(job.job_id)
    assert event["payload_ref"] == job.payload_ref == outbox.payload["payload_ref"]
    payload = service._load_payload_ref(
        job.payload_ref, kind="runtime.control_job_payload.workflow_run"
    )
    assert payload["state_payload"]["inputs"]["input_bindings_ref"] == selected.model_dump(
        mode="json"
    )


def test_workflow_source_preserves_exact_registered_sql_transport() -> None:
    selected = {
        "artifact_id": _SHA_A,
        "kind": "fabric.registered_sql_admission_binding",
        "media_type": "application/json",
        "manifest_profile_sha256": _SHA_B,
    }
    source = WorkflowDataSourceBinding.model_validate({"registered_sql_admission_ref": selected})
    key, ref, intent = _resolve_workflow_data_source(source)
    assert key == "registered_sql_admission_ref"
    assert ref.model_dump(mode="json") == selected
    assert intent is None
    with pytest.raises(ValidationError):
        WorkflowDataSourceBinding.model_validate(
            {"registered_sql_admission_ref": selected, "data_snapshot_ref": _SHA_A}
        )
    with pytest.raises(ValidationError):
        WorkflowDataSourceBinding.model_validate(
            {"registered_sql_admission_ref": {**selected, "manifest_profile_sha256": None}}
        )


def test_workflow_source_rejects_unselected_or_wrong_foundry_binding() -> None:
    for ref in (
        {"artifact_id": _SHA_A, "kind": "foundry.input_bindings", "media_type": "application/json"},
        {
            "artifact_id": _SHA_A,
            "kind": "other",
            "media_type": "application/json",
            "manifest_profile_sha256": _SHA_B,
        },
        {
            "artifact_id": _SHA_A,
            "kind": "foundry.input_bindings",
            "media_type": "text/plain",
            "manifest_profile_sha256": _SHA_B,
        },
    ):
        with pytest.raises(ValidationError):
            WorkflowDataSourceBinding.model_validate({"input_bindings_ref": ref})


@pytest.mark.parametrize(
    "value",
    [
        {"data_view_request_ref": None},
        {"data_view_request_ref": {"artifact_id": _SHA_A, "media_type": "application/json"}},
        {"data_view_request_ref": {"artifact_id": _SHA_A, "kind": "ir.data_view_request"}},
        {
            "data_view_request_ref": {
                "artifact_id": _SHA_A,
                "kind": "ir.data_view_request",
                "media_type": "application/json",
                "manifest_profile_sha256": None,
            }
        },
        {
            "data_view_request_ref": {
                "artifact_id": _SHA_A,
                "kind": "fabric.data_view_request",
                "media_type": "application/json",
            }
        },
        {
            "data_view_request_ref": {
                "artifact_id": _SHA_A,
                "kind": "ir.data_view_request",
                "media_type": "text/plain",
            }
        },
        {"data_snapshot_ref": _SHA_A, "data_view_request_ref": _SHA_B},
    ],
)
def test_workflow_source_refuses_malformed_or_ambiguous_selector(value: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WorkflowDataSourceBinding.model_validate(value)


class _ControlJobStore:
    def __init__(self, job: SimpleNamespace, event_payload: dict[str, Any]) -> None:
        self.job = job
        self.event_payload = deepcopy(event_payload)
        self.outbox = SimpleNamespace(
            topic="control.job.created",
            job_id=job.job_id,
            run_id=job.run_id,
            payload=deepcopy(event_payload),
        )

    def get_job(self, job_id: str) -> SimpleNamespace | None:
        return self.job if job_id == self.job.job_id else None

    def get_job_created_event_payload(self, job_id: str) -> dict[str, Any]:
        return self.event_payload

    def get_job_created_outbox_event(self, job_id: str) -> SimpleNamespace:
        return self.outbox


def _persist_job_origin(
    store: FileSystemCAS,
    original: DataViewRequestRef | None,
    current: DataViewRequestRef | None,
    profile_origin: str | None,
) -> tuple[_ControlJobStore, str, dict[str, Any]]:
    run_id, job_id = "run-profile-origin", "job-profile-origin"
    source_inputs = (
        {"data_view_request_ref": original.model_dump(mode="json")}
        if original is not None
        else {"data_snapshot_ref": _SHA_A}
    )
    payload = {
        "run_id": run_id,
        "state_payload": {"run_id": run_id, "inputs": source_inputs, "params": {}},
    }
    if profile_origin is not None:
        payload["data_view_request_intent"] = {
            "schema_version": "polisyos.runtime.workflow_data_view_request_intent.v1",
            "profile_origin": profile_origin,
        }
    payload_ref = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="runtime.control_job_payload.workflow_run",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.runtime.ControlJobPayload", version="1.0"),
        ),
    )
    job = SimpleNamespace(
        job_id=job_id,
        run_id=run_id,
        kind="workflow_run",
        pipeline_id=None,
        payload_ref=str(payload_ref.artifact_id),
        submitted_by="fixture",
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={"allow_mock_fallback": False},
    )
    event = {
        "job_id": job.job_id,
        "run_id": job.run_id,
        "job_kind": job.kind,
        "pipeline_id": job.pipeline_id,
        "payload_ref": job.payload_ref,
        "submitted_by": job.submitted_by,
        "requested_execution_profile": job.requested_execution_profile,
        "effective_execution_profile": job.effective_execution_profile,
        "policy_flags": job.policy_flags,
    }
    state_inputs = (
        {"data_view_request_ref": current.model_dump(mode="json")}
        if current is not None
        else {"data_snapshot_ref": _SHA_A}
    )
    return (
        _ControlJobStore(job, event),
        job_id,
        {"run_id": run_id, "inputs": state_inputs, "params": {}},
    )


def test_profile_origin_requires_exact_event_and_reconciles_selected_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    profile_a = _profiled_request(store, "same-bytes-profile-a")
    profile_b = _profiled_request(store, "same-bytes-profile-b")
    assert profile_a.artifact_id == profile_b.artifact_id
    assert profile_a.manifest_profile_sha256 != profile_b.manifest_profile_sha256

    control, job_id, state = _persist_job_origin(store, profile_a, profile_b, "caller_selected")
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "not_established"
    assert issue == "data_view_request_profile_origin_not_established"

    control, job_id, state = _persist_job_origin(store, profile_a, profile_a, "caller_selected")
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "caller_selected"
    assert issue is None

    legacy = DataViewRequestRef(
        artifact_id=profile_a.artifact_id,
        kind=profile_a.kind,
        media_type=profile_a.media_type,
    )
    control, job_id, state = _persist_job_origin(store, legacy, profile_b, "worker_default")
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "worker_default"
    assert issue is None

    control.event_payload["payload_ref"] = _SHA_B
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "not_established"
    assert issue == "data_view_request_profile_origin_not_established"

    control, job_id, state = _persist_job_origin(store, legacy, profile_b, "worker_default")
    control.outbox.payload["payload_ref"] = _SHA_B
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "not_established"
    assert issue == "data_view_request_profile_origin_not_established"


def test_profile_origin_does_not_trust_profile_self_label_and_reports_no_request(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path)
    profileless = DataViewRequestRef(
        artifact_id=_SHA_A, kind="ir.data_view_request", media_type="application/json"
    )
    selected = DataViewRequestRef(
        artifact_id=_SHA_A,
        kind="ir.data_view_request",
        media_type="application/json",
        manifest_profile_sha256=_SHA_B,
    )
    control, job_id, state = _persist_job_origin(store, profileless, selected, "caller_selected")
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "not_established"
    assert issue == "data_view_request_profile_origin_not_established"

    control, job_id, state = _persist_job_origin(store, None, None, None)
    origin, issue = _workflow_data_view_request_profile_origin(
        store=store, control_job_store=control, control_job_id=job_id, state_payload=state
    )
    assert origin == "not_requested"
    assert issue is None
