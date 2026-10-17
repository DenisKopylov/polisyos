from __future__ import annotations

import json
import math
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import profile_bound_ref
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.fabric import DataSnapshot, DataViewRequestRef
from polisyos.core.contracts.foundry import FoundryInputBindings
from polisyos.core.registry import build_default_registry_bundle
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.foundry._internal.quickstart import (
    build_trivial_trinity_bundle,
    put_trivial_trinity_bundle,
)
from polisyos.ir.linker.reports import LinkReport
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.scientist.orchestration.engine.checkpoint import (
    load_checkpoint,
    load_checkpoint_head,
)
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec
from tests._helpers.runtime_http import _runtime_api_request

pytest_plugins = ("tests._helpers.runtime_http",)


# Twice the measured 328s controlled N4 route duration is a test-harness ceiling.
# The default workflow's wall time remains unmeasured; this is not a product SLA.
_CONTROL_JOB_TEST_WAIT_BUDGET_SECONDS = 656.0
_CONTROL_JOB_POLL_INTERVAL_SECONDS = 0.1


def _wait_for_control_job_terminal(
    get_job: Callable[[str], Any | None],
    job_id: str,
    *,
    timeout_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Wait for a durable control job to complete, fail, or exhaust its test budget."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Control-job test wait budget must be finite and positive.")

    deadline = monotonic() + timeout_seconds
    while True:
        job = get_job(job_id)
        if job is None:
            raise AssertionError(f"Control job {job_id!r} disappeared while waiting.")
        if job.state == "completed":
            return job
        if job.state == "failed":
            detail = job.error_message or "no error message recorded"
            raise AssertionError(f"Control job {job_id!r} failed: {detail}")
        if job.state not in {"pending", "running"}:
            raise AssertionError(f"Control job {job_id!r} reached unexpected state {job.state!r}.")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Control job {job_id!r} remained {job.state!r} after "
                f"{timeout_seconds:g}s test wait budget."
            )
        sleep(min(_CONTROL_JOB_POLL_INTERVAL_SECONDS, remaining))


def test_control_job_wait_returns_completed_record_without_wall_sleep() -> None:
    states = iter(("pending", "running", "completed"))
    clock = [0.0]
    lookups: list[str] = []

    def get_job(job_id: str) -> SimpleNamespace:
        lookups.append(job_id)
        return SimpleNamespace(state=next(states), error_message=None)

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    completed = _wait_for_control_job_terminal(
        get_job,
        "job-completes",
        timeout_seconds=1.0,
        monotonic=lambda: clock[0],
        sleep=sleep,
    )

    assert completed.state == "completed"
    assert lookups == ["job-completes"] * 3
    assert clock[0] == pytest.approx(0.2)


def test_control_job_wait_times_out_for_stalled_worker_without_wall_sleep() -> None:
    clock = [0.0]
    lookups = 0

    def get_job(job_id: str) -> SimpleNamespace:
        nonlocal lookups
        lookups += 1
        return SimpleNamespace(state="running", error_message=None)

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    with pytest.raises(TimeoutError, match=r"job-stalled.*'running'.*0.25s"):
        _wait_for_control_job_terminal(
            get_job,
            "job-stalled",
            timeout_seconds=0.25,
            monotonic=lambda: clock[0],
            sleep=sleep,
        )

    assert lookups == 4
    assert clock[0] == pytest.approx(0.25)


def test_control_job_wait_reports_worker_failure_immediately() -> None:
    monotonic_calls = 0
    sleeps: list[float] = []

    def get_job(job_id: str) -> SimpleNamespace:
        return SimpleNamespace(state="failed", error_message="worker exploded")

    def monotonic() -> float:
        nonlocal monotonic_calls
        monotonic_calls += 1
        return 0.0

    with pytest.raises(AssertionError, match=r"job-failed.*worker exploded"):
        _wait_for_control_job_terminal(
            get_job,
            "job-failed",
            timeout_seconds=656.0,
            monotonic=monotonic,
            sleep=sleeps.append,
        )

    assert monotonic_calls == 1
    assert sleeps == []


@pytest.mark.parametrize(
    "timeout_seconds",
    [float("nan"), float("inf"), float("-inf"), 0.0, -1.0],
)
def test_control_job_wait_rejects_nonfinite_or_nonpositive_budget(
    timeout_seconds: float,
) -> None:
    calls: list[str] = []

    def get_job(job_id: str) -> SimpleNamespace:
        calls.append("get_job")
        return SimpleNamespace(state="running", error_message=None)

    def monotonic() -> float:
        calls.append("monotonic")
        return 0.0

    def sleep(seconds: float) -> None:
        calls.append("sleep")

    with pytest.raises(ValueError, match="finite and positive"):
        _wait_for_control_job_terminal(
            get_job,
            "job-invalid-budget",
            timeout_seconds=timeout_seconds,
            monotonic=monotonic,
            sleep=sleep,
        )

    assert calls == []


def _persist_request(store, version: str) -> DataViewRequestRef:
    request = DataViewRequest(
        schema_version="1.0",
        request_id="workflow-post-profile-selection",
        view_type="table",
        metrics=["policy_inputs"],
    )
    ref = store.put_json(
        request,
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
    return DataViewRequestRef.model_validate(profile_bound_ref(store, ref).model_dump(mode="json"))


def _persist_trinity_bundle(store: ArtifactStore) -> ArtifactRef:
    """Produce one typed Trinity fixture through the existing CAS-backed APIs."""
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    bundle = build_trivial_trinity_bundle(str(registry_bundle_ref.artifact_id))
    return put_trivial_trinity_bundle(store, bundle)


def _load_verified_artifact_payload(
    runtime_api_env: dict[str, Any],
    store: ArtifactStore,
    raw_ref: dict[str, Any],
) -> tuple[ArtifactRef, Any, ArtifactManifest]:
    """Read one exact typed CAS view and its verified JSON payload under the fixture owner."""
    ref = ArtifactRef.model_validate(raw_ref)
    verification = _runtime_api_request(runtime_api_env, store.verify, ref)
    assert verification.ok, verification.error
    payload = from_canonical_bytes(_runtime_api_request(runtime_api_env, store.get_bytes, ref))
    manifest = _runtime_api_request(runtime_api_env, store.get_manifest, ref)
    assert manifest.artifact_id == ref.artifact_id
    assert manifest.kind == ref.kind
    assert manifest.media_type == ref.media_type
    return ref, payload, manifest


def _assert_manifest_input(
    manifest: ArtifactManifest,
    role: str,
    expected: ArtifactRef,
) -> None:
    matches = [item for item in manifest.inputs if item.role == role]
    assert len(matches) == 1
    actual: InputRef = matches[0]
    assert actual.artifact_id == expected.artifact_id
    assert actual.manifest_profile_sha256 == expected.manifest_profile_sha256


def test_ordinary_post_worker_fabric_cas_and_fresh_get_keep_selected_profile(
    tmp_path: Path,
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = runtime_api_env["app"].state._control_service
    worker = service._worker
    assert worker is not None
    assert worker._thread is not None and worker._thread.is_alive()
    store = service._artifact_store
    database = tmp_path / "workflow-post-input.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs (metric TEXT NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES ('selected-profile-path')")

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{database}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    fabric_api = __import__("polisyos.fabric.api", fromlist=["fabric_get_data"])
    monkeypatch.setattr(fabric_api, "_default_connector_registry", lambda: registry)

    try:
        selected_a = _runtime_api_request(
            runtime_api_env, _persist_request, store, "source-profile-a"
        )
        selected_b = _runtime_api_request(
            runtime_api_env, _persist_request, store, "source-profile-b"
        )
        trinity_ref = _runtime_api_request(runtime_api_env, _persist_trinity_bundle, store)
        assert selected_a.artifact_id == selected_b.artifact_id
        assert selected_a.manifest_profile_sha256 != selected_b.manifest_profile_sha256

        response = runtime_api_env["client"].post(
            "/api/v1/control/runs",
            json={
                "data_source": {"data_view_request_ref": selected_a.model_dump(mode="json")},
                "trinity_bundle_ref": str(trinity_ref.artifact_id),
                "params": {
                    "control_plane_transition": "legacy_shadow",
                    "workflow_id": "scientist_default",
                    "data_view_request_profile_status": "worker_default_limited",
                },
            },
        )
        assert response.status_code == 200, response.text
        launch = response.json()
        job_id, run_id = launch["job_id"], launch["run_id"]
        job = service._control_store.get_job(job_id)
        assert job is not None
        assert job.payload_ref is not None
        payload = _runtime_api_request(
            runtime_api_env,
            service._load_payload_ref,
            job.payload_ref,
            kind="runtime.control_job_payload.workflow_run",
        )
        original = payload["state_payload"]["inputs"]["data_view_request_ref"]
        assert original["manifest_profile_sha256"] == selected_a.manifest_profile_sha256
        assert payload["data_view_request_intent"]["profile_origin"] == "caller_selected"
        bound_trinity = payload["state_payload"]["inputs"]["trinity_bundle_ref"]
        assert bound_trinity["artifact_id"] == str(trinity_ref.artifact_id)
        assert bound_trinity["kind"] == "ir.trinity_bundle"
        assert bound_trinity["media_type"] == "application/json"

        finished = _wait_for_control_job_terminal(
            service._control_store.get_job,
            job_id,
            timeout_seconds=_CONTROL_JOB_TEST_WAIT_BUDGET_SECONDS,
        )
        assert finished.state == "completed"
        assert worker._thread is not None and worker._thread.is_alive()
        evidence = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/evidence-context")
        assert evidence.status_code == 200, evidence.text
        context = evidence.json()["context"]
        assert context["data_view_request_ref"]["artifact_id"] == str(selected_a.artifact_id)
        assert (
            context["data_view_request_ref"]["manifest_profile_sha256"]
            == selected_a.manifest_profile_sha256
        )
        assert context["data_snapshot_ref"]["manifest_profile_sha256"]
        assert context["data_view_request_profile_status"] == "caller_selected_profile"

        run_dir = service._core_runs_root / run_id
        head = load_checkpoint_head(run_dir)
        assert head is not None
        assert head.run_id == run_id
        checkpoint = _runtime_api_request(
            runtime_api_env, load_checkpoint, store, head.checkpoint_ref
        )
        assert checkpoint.metadata.run_id == run_id
        assert checkpoint.metadata.snapshot_mode == "full"
        assert checkpoint.metadata.completed_node_status_contract == "native_node_outcome_v1"
        state = checkpoint.state
        assert state is not None
        input_refs = state["inputs"]
        artifact_refs = state["artifacts_index"]
        report_refs = state["reports_index"]

        source_ref = ArtifactRef.model_validate(input_refs["data_view_request_ref"])
        selected_a_ref = ArtifactRef.model_validate(selected_a.model_dump(mode="json"))
        selected_b_ref = ArtifactRef.model_validate(selected_b.model_dump(mode="json"))
        assert source_ref == selected_a_ref
        assert selected_a_ref.artifact_id == selected_b_ref.artifact_id
        assert selected_a_ref.manifest_profile_sha256 != selected_b_ref.manifest_profile_sha256
        fresh_get_source_ref = ArtifactRef.model_validate(context["data_view_request_ref"])
        assert fresh_get_source_ref == source_ref

        snapshot_ref, snapshot_payload, snapshot_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, input_refs["data_snapshot_ref"]
        )
        assert ArtifactRef.model_validate(context["data_snapshot_ref"]) == snapshot_ref
        snapshot = DataSnapshot.model_validate(snapshot_payload)
        assert snapshot.model_dump(mode="json", exclude_none=True) == snapshot_payload
        _assert_manifest_input(snapshot_manifest, "data_view_request_ref", source_ref)
        request_edge = next(
            item for item in snapshot_manifest.inputs if item.role == "data_view_request_ref"
        )
        assert request_edge.manifest_profile_sha256 != selected_b_ref.manifest_profile_sha256

        data_ref, rows, data_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, snapshot.data_ref.model_dump(mode="json")
        )
        assert data_ref.kind == "fabric.tabular_payload"
        assert rows == [{"metric": "selected-profile-path"}]
        _assert_manifest_input(data_manifest, "data_view_request_ref", source_ref)
        for child_ref in (
            snapshot.data_schema_ref,
            snapshot.quality_report_ref,
            snapshot.warnings_ref,
        ):
            if child_ref is None:
                continue
            child_verification = _runtime_api_request(runtime_api_env, store.verify, child_ref)
            assert child_verification.ok, child_verification.error

        registry_ref = ArtifactRef.model_validate(input_refs["registry_bundle_ref"])
        bindings_ref, bindings_payload, bindings_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, input_refs["input_bindings_ref"]
        )
        bindings = FoundryInputBindings.model_validate(bindings_payload)
        assert bindings.model_dump(mode="json") == bindings_payload
        assert bindings.data_snapshot_ref == snapshot_ref
        assert bindings.registry_bundle_ref == registry_ref
        _assert_manifest_input(bindings_manifest, "input.data_snapshot_ref", snapshot_ref)
        _assert_manifest_input(bindings_manifest, "input.registry_bundle_ref", registry_ref)

        binding_report_ref, binding_report, binding_report_manifest = (
            _load_verified_artifact_payload(
                runtime_api_env, store, artifact_refs["input_binding_report_ref"]
            )
        )
        assert binding_report["data_snapshot_ref"] == snapshot_ref.model_dump(mode="json")
        assert binding_report["registry_bundle_ref"] == registry_ref.model_dump(mode="json")
        assert binding_report["rule_count"] == len(bindings.rules) == 0
        assert binding_report["applied_binding_ids"] == []
        _assert_manifest_input(binding_report_manifest, "input.data_snapshot_ref", snapshot_ref)

        trinity_ref = ArtifactRef.model_validate(input_refs["trinity_bundle_ref"])
        link_ref, link_payload, link_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, report_refs["link_report_ref"]
        )
        link_report = LinkReport.model_validate(link_payload)
        assert link_ref.manifest_profile_sha256 is not None
        assert link_report.model_dump(mode="json") == link_payload
        assert link_report.ok is True
        _assert_manifest_input(link_manifest, "ir", trinity_ref)
        _assert_manifest_input(link_manifest, "registry_bundle", registry_ref)

        def _node_link_output(alias: str) -> ArtifactRef:
            matches = [
                ArtifactRef.model_validate(output)
                for record in node_records
                if record["phase"] == f"scientist.node.{alias}" and record["event"] == "NODE_OK"
                for output in record.get("refs", {}).get("outputs", [])
                if output.get("kind") == "compiler.link_report"
            ]
            assert len(matches) == 1
            return matches[0]

        assert _node_link_output("link_trinity") == link_ref
        assert _node_link_output("compile_foundry") == link_ref

        compile_ref, compile_payload, compile_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, report_refs["compile_report_ref"]
        )
        compile_report = CompileReport.model_validate(compile_payload)
        assert compile_report.model_dump(mode="json") == compile_payload
        assert compile_report.ok is True
        assert compile_report.policy_ref == trinity_ref
        assert compile_report.registry_bundle_ref == registry_ref
        assert compile_report.link_report_ref == link_ref
        _assert_manifest_input(compile_manifest, "ir", trinity_ref)
        _assert_manifest_input(compile_manifest, "registry_bundle", registry_ref)
        _assert_manifest_input(compile_manifest, "link_report", link_ref)

        packet_ref, packet_payload, packet_manifest = _load_verified_artifact_payload(
            runtime_api_env, store, artifact_refs["decision_packet_ref"]
        )
        packet_inputs = packet_payload["inputs"]
        assert packet_inputs["data_snapshot_ref"] == str(snapshot_ref.artifact_id)
        assert packet_inputs["input_bindings_ref"] == str(bindings_ref.artifact_id)
        assert packet_inputs["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
        assert packet_inputs["registry_bundle_ref"] == str(registry_ref.artifact_id)
        # The packet edge preserves the exact manifest view produced by Fabric.
        _assert_manifest_input(packet_manifest, "input.data_snapshot_ref", snapshot_ref)
        _assert_manifest_input(packet_manifest, "input.input_bindings_ref", bindings_ref)

        trace_records = [
            json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines() if line
        ]
        node_records = [
            record
            for record in trace_records
            if record.get("event") in {"NODE_OK", "NODE_SKIP", "NODE_FAIL"}
            and str(record.get("phase", "")).startswith("scientist.node.")
        ]
        default_aliases = {invocation.alias for invocation in default_workflow_spec().nodes}
        recorded_aliases = {
            record["phase"].removeprefix("scientist.node.") for record in node_records
        }
        assert len(default_aliases) == 23
        assert recorded_aliases == default_aliases
        successful_nodes = {
            record["phase"].removeprefix("scientist.node.")
            for record in node_records
            if record["event"] == "NODE_OK"
        }
        skipped_nodes = {
            record["phase"].removeprefix("scientist.node.")
            for record in node_records
            if record["event"] == "NODE_SKIP"
        }
        assert not any(record["event"] == "NODE_FAIL" for record in node_records)
        assert set(checkpoint.metadata.completed_nodes) == successful_nodes
        required_successes = {
            "build_data_snapshot",
            "bind_foundry_inputs",
            "link_trinity",
            "compile_foundry",
            "run_simulation",
            "build_decision_packet",
        }
        assert required_successes <= successful_nodes
        assert required_successes.isdisjoint(skipped_nodes)

        expected_node_outputs = {
            "build_data_snapshot": {str(snapshot_ref.artifact_id)},
            "bind_foundry_inputs": {
                str(bindings_ref.artifact_id),
                str(binding_report_ref.artifact_id),
            },
            "link_trinity": {str(link_ref.artifact_id)},
            "compile_foundry": {str(compile_ref.artifact_id)},
            "run_simulation": {str(artifact_refs["simulation_result_ref"]["artifact_id"])},
            "build_decision_packet": {str(packet_ref.artifact_id)},
        }
        for alias, expected_ids in expected_node_outputs.items():
            matching = [
                record
                for record in node_records
                if record["phase"] == f"scientist.node.{alias}" and record["event"] == "NODE_OK"
            ]
            assert matching
            emitted_ids = {
                str(ref["artifact_id"])
                for record in matching
                for ref in record.get("refs", {}).get("outputs", [])
            }
            assert expected_ids <= emitted_ids
    finally:
        registry.shutdown()
