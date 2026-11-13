from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

import polisyos.runtime.http.services.control_plane_store as store_module
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)


def _types() -> tuple[type[Any], type[Any], type[Any]]:
    key_type = getattr(store_module, "AcquisitionEvaluationFrontierKey", None)
    value_type = getattr(store_module, "AcquisitionEvaluationFrontierValue", None)
    cas_type = getattr(store_module, "AcquisitionEvaluationFrontierCAS", None)
    assert key_type is not None, "ControlStore must expose its selected-evaluation owner key"
    assert value_type is not None, "ControlStore must expose its selected-evaluation owner value"
    assert cas_type is not None, "ControlStore must expose its revision/ref CAS"
    return key_type, value_type, cas_type


def _sha(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _selected_receipt_ref(tmp_path: Path, label: str, *, version: str = "3") -> ArtifactRef:
    return FileSystemCAS(tmp_path / "receipt-cas").put_json(
        {"receipt": label},
        ArtifactWriteOptions(
            kind="runtime.acquisition_action_receipt",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.runtime.acquisition_action_receipt", version=version),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _scope(tenant: str = "tenant-a", cell: str = "cell-a") -> dict[str, object]:
    return {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": tenant,
        "cell_id": cell,
        "actor_subject": "tester",
        "actor_authenticated": True,
        "actor_roles": ["operator"],
    }


def _create_job(
    store: ControlPlaneStore, *, job_id: str, kind: str, run_id: str
) -> ControlJobRecord:
    payload = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": kind,
        "pipeline_id": None,
        "payload_ref": _sha(f"{job_id}:payload"),
        "submitted_by": "tester",
        "requested_execution_profile": None,
        "effective_execution_profile": "governed",
        "policy_flags": {},
        "capability_manifest_ref": _sha(f"{job_id}:manifest"),
        "execution_scope": _scope(),
    }
    return store.create_job(
        job_id=job_id,
        kind=kind,
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="governed",
        policy_flags={},
        capability_manifest_ref=payload["capability_manifest_ref"],
        payload_ref=payload["payload_ref"],
        submitted_by="tester",
        creation_event_payload=payload,
    )


def _lease_job(store: ControlPlaneStore, job: ControlJobRecord, worker_id: str) -> tuple[str, int]:
    leased = store.lease_next_job(worker_id=worker_id, lease_seconds=60)
    assert leased is not None
    assert leased.job_id == job.job_id
    return worker_id, leased.attempt


def _key(source_job_id: str = "source-nl", *, candidate: str = "candidate-a") -> Any:
    key_type, _, _ = _types()
    return key_type(
        tenant_id="tenant-a",
        cell_id="cell-a",
        source_job_id=source_job_id,
        design_problem_ref=_sha("design"),
        candidate_id=candidate,
    )


def _value(witness: str = "compiled-a", tuple_label: str = "selected-tuple-a") -> Any:
    _, value_type, _ = _types()
    return value_type(
        selected_evaluation_witness_ref=_sha(witness),
        selected_evaluation_content_hash=_sha(tuple_label),
        basis_ref=_sha("basis-a"),
        basis_content_hash=_sha("basis-content-a"),
        decision_ref=_sha("decision-a"),
    )


def _bootstrap(
    store: ControlPlaneStore, tmp_path: Path, *, source_job_id: str = "source-nl"
) -> tuple[ControlJobRecord, Any, dict[str, object]]:
    _, _, cas_type = _types()
    job = _create_job(store, job_id=source_job_id, kind="natural_language_run", run_id="run-a")
    worker_id, attempt = _lease_job(store, job, f"worker-{source_job_id}")
    value = _value()
    compiled_id = value.selected_evaluation_witness_ref
    progress = {
        "compiled_recursive_generation_cycle_ref": compiled_id,
        "compiled_recursive_generation_cycle_artifact_ref": {
            "artifact_id": compiled_id,
            "kind": "runtime.compiled_recursive_generation_cycle",
            "media_type": "application/json",
        },
    }
    cas = cas_type(
        key=_key(source_job_id),
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=value,
    )
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt):
        result = store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress=progress,
            selected_evaluation_frontier_cas=cas,
        )
    assert result is not None
    assert result.revision == 1
    return job, result, progress


def _create_action_job(
    store: ControlPlaneStore, *, job_id: str, run_id: str = "run-a"
) -> tuple[ControlJobRecord, str, int]:
    job = _create_job(store, job_id=job_id, kind="acquisition", run_id=run_id)
    worker_id, attempt = _lease_job(store, job, f"worker-{job_id}")
    return job, worker_id, attempt


def _append_action(
    store: ControlPlaneStore,
    *,
    job: ControlJobRecord,
    worker_id: str,
    attempt: int,
    key: Any,
    expected_revision: int,
    expected_ref: str | None,
    route_id: str,
    replacement: Any,
    receipt_ref: str | None = None,
    receipt_manifest_profile_sha256: str | None = None,
) -> Any:
    _, _, cas_type = _types()
    cas = cas_type(
        key=key,
        expected_revision=expected_revision,
        expected_frontier_ref=expected_ref,
        replacement=replacement,
    )
    selected_receipt_ref = receipt_ref or _sha(f"{route_id}:receipt")
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt):
        return store.advance_acquisition_action_head_with_frontier(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=_sha(route_id),
            action_generation=1,
            expected_head_generation=0,
            receipt_ref=selected_receipt_ref,
            receipt_sha256=selected_receipt_ref,
            durable_event_id=f"event-{route_id}",
            coarse_phase="completed",
            receipt_phase="completed",
            recovery_state="none",
            job_id=job.job_id,
            predecessor_receipt_ref=None,
            frontier_cas=cas,
            receipt_manifest_profile_sha256=receipt_manifest_profile_sha256,
        )


def test_frontier_bootstrap_is_owner_fenced_and_history_is_immutable(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "frontier.sqlite3")
    _, record, _ = _bootstrap(store, tmp_path)

    assert store.read_acquisition_evaluation_frontier(record.key) == record
    assert store.get_acquisition_evaluation_frontier_by_ref(record.frontier_ref) == record
    assert (
        store.read_acquisition_evaluation_frontier(_key("source-nl", candidate="unseen-candidate"))
        is None
    )


def test_absent_frontier_check_only_commits_action_head_without_advancing_frontier(
    tmp_path: Path,
) -> None:
    """A blocked terminal can atomically attest an empty frontier preimage."""
    _, _, cas_type = _types()
    path = tmp_path / "absent-check-only.sqlite3"
    writer = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    reader = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    key = _key("source-blocked")
    source_job = _create_job(
        writer, job_id=key.source_job_id, kind="natural_language_run", run_id="run-a"
    )
    source_worker, source_attempt = _lease_job(writer, source_job, "worker-source-blocked")
    with writer.job_execution_fence(
        job_id=source_job.job_id, worker_id=source_worker, attempt=source_attempt
    ):
        writer.complete_job(
            job_id=source_job.job_id,
            run_id="run-a",
            progress={
                "compiled_recursive_generation_cycle_ref": _sha("blocked-source-output"),
                "compiled_recursive_generation_cycle_artifact_ref": {
                    "artifact_id": _sha("blocked-source-output"),
                    "kind": "runtime.compiled_recursive_generation_cycle",
                    "media_type": "application/json",
                },
            },
        )
    job, worker, attempt = _create_action_job(writer, job_id="action-blocked")
    route_id = _sha("blocked-route")
    pending_ref = _sha("pending-phase")
    with writer.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        pending = writer.advance_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=route_id,
            action_generation=1,
            expected_head_generation=0,
            receipt_ref=pending_ref,
            receipt_sha256=pending_ref,
            durable_event_id="event-pending",
            coarse_phase="candidate_input_reentry_pending",
            receipt_phase="candidate_input_reentry_pending",
            recovery_state="none",
            job_id=job.job_id,
            predecessor_receipt_ref=None,
        )
    cas = cas_type(
        key=key,
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=None,
    )
    receipt_ref = _sha("blocked-terminal")
    with writer.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        head = writer.advance_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=route_id,
            action_generation=1,
            expected_head_generation=pending.head_generation,
            receipt_ref=receipt_ref,
            receipt_sha256=receipt_ref,
            durable_event_id="event-blocked-terminal",
            coarse_phase="terminal",
            receipt_phase="terminal",
            recovery_state="complete",
            job_id=job.job_id,
            predecessor_receipt_ref=pending.receipt_ref,
            frontier_cas=cas,
        )

    assert head.evaluation_frontier_before_ref is None
    assert head.evaluation_frontier_ref is None
    assert reader.read_acquisition_evaluation_frontier(key) is None
    assert (
        reader.get_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=route_id,
            action_generation=1,
        )
        == head
    )


def test_absent_frontier_check_only_conflict_rolls_back_action_head(tmp_path: Path) -> None:
    """An absent-preimage check fails if another connection selected a frontier."""
    _, _, cas_type = _types()
    path = tmp_path / "absent-check-conflict.sqlite3"
    writer = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    reader = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    key = _key("source-check-conflict")
    source_job = _create_job(
        writer, job_id="source-check-conflict", kind="natural_language_run", run_id="run-a"
    )
    source_worker, source_attempt = _lease_job(writer, source_job, "worker-source-check-conflict")
    value = _value()
    output_ref = value.selected_evaluation_witness_ref
    cas_initial = cas_type(
        key=key,
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=value,
    )
    with writer.job_execution_fence(
        job_id=source_job.job_id, worker_id=source_worker, attempt=source_attempt
    ):
        selected = writer.complete_job(
            job_id=source_job.job_id,
            run_id="run-a",
            progress={
                "compiled_recursive_generation_cycle_ref": output_ref,
                "compiled_recursive_generation_cycle_artifact_ref": {
                    "artifact_id": output_ref,
                    "kind": "runtime.compiled_recursive_generation_cycle",
                    "media_type": "application/json",
                },
            },
            selected_evaluation_frontier_cas=cas_initial,
        )
    assert selected is not None
    blocked_job, worker, attempt = _create_action_job(reader, job_id="action-absent-conflict")
    blocked = cas_type(
        key=key,
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=None,
    )
    receipt_ref = _sha("must-rollback-blocked-terminal")
    with (
        reader.job_execution_fence(job_id=blocked_job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="frontier_conflict"),
    ):
        reader.advance_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=_sha("blocked-conflict-route"),
            action_generation=1,
            expected_head_generation=0,
            receipt_ref=receipt_ref,
            receipt_sha256=receipt_ref,
            durable_event_id="event-absent-conflict",
            coarse_phase="terminal",
            receipt_phase="terminal",
            recovery_state="complete",
            job_id=blocked_job.job_id,
            predecessor_receipt_ref=_sha("pending-phase"),
            frontier_cas=blocked,
        )

    assert writer.read_acquisition_evaluation_frontier(key) == selected
    assert (
        reader.get_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=_sha("blocked-conflict-route"),
            action_generation=1,
        )
        is None
    )


def test_bootstrap_rolls_back_when_witness_is_not_the_completed_output(tmp_path: Path) -> None:
    _, _, cas_type = _types()
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "bad-output.sqlite3")
    job = _create_job(store, job_id="source-nl", kind="natural_language_run", run_id="run-a")
    worker_id, attempt = _lease_job(store, job, "worker-source")
    wrong_value = _value("not-the-output")
    output_ref = _value().selected_evaluation_witness_ref
    progress = {
        "compiled_recursive_generation_cycle_ref": output_ref,
        "compiled_recursive_generation_cycle_artifact_ref": {
            "artifact_id": output_ref,
            "kind": "runtime.compiled_recursive_generation_cycle",
            "media_type": "application/json",
        },
    }
    cas = cas_type(
        key=_key(),
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=wrong_value,
    )
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt),
        pytest.raises(ValueError, match="completed_output_mismatch"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress=progress,
            selected_evaluation_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "running"
    assert store.read_acquisition_evaluation_frontier(_key()) is None


def test_frontier_cas_rolls_back_failed_completion(tmp_path: Path) -> None:
    _, _, cas_type = _types()
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "failed-completion.sqlite3")
    job = _create_job(store, job_id="source-nl", kind="natural_language_run", run_id="run-a")
    worker_id, attempt = _lease_job(store, job, "worker-source")
    value = _value()
    compiled_id = value.selected_evaluation_witness_ref
    cas = cas_type(
        key=_key(),
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=value,
    )
    progress = {
        "status": "failed",
        "compiled_recursive_generation_cycle_ref": compiled_id,
        "compiled_recursive_generation_cycle_artifact_ref": {
            "artifact_id": compiled_id,
            "kind": "runtime.compiled_recursive_generation_cycle",
            "media_type": "application/json",
        },
    }
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt),
        pytest.raises(ValueError, match="completion_not_successful"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress=progress,
            selected_evaluation_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "running"
    assert store.read_acquisition_evaluation_frontier(_key()) is None


def test_sibling_action_reentry_cas_conflict_preserves_head_and_history(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "sibling.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    key = initial.key
    first_job, first_worker, first_attempt = _create_action_job(store, job_id="action-a")
    second_job, second_worker, second_attempt = _create_action_job(store, job_id="action-b")

    replacement = _value("compiled-b", "selected-tuple-b")
    advanced = _append_action(
        store,
        job=first_job,
        worker_id=first_worker,
        attempt=first_attempt,
        key=key,
        expected_revision=1,
        expected_ref=initial.frontier_ref,
        route_id="route-a",
        replacement=replacement,
    )
    assert advanced.frontier.revision == 2
    assert store.get_acquisition_evaluation_frontier_by_ref(initial.frontier_ref) == initial
    current = store.read_acquisition_evaluation_frontier(key)
    assert current == advanced.frontier

    with pytest.raises(ValueError, match="frontier_conflict"):
        _append_action(
            store,
            job=second_job,
            worker_id=second_worker,
            attempt=second_attempt,
            key=key,
            expected_revision=1,
            expected_ref=initial.frontier_ref,
            route_id="route-b",
            replacement=None,
        )
    assert (
        store.get_acquisition_action_head(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=_sha("route-b"),
            action_generation=1,
        )
        is None
    )


@pytest.mark.parametrize(
    ("expected_revision", "expected_ref"),
    [
        (1, _sha("wrong-ref")),
        (2, _sha("current-frontier-ref")),
    ],
)
def test_frontier_cas_checks_revision_and_ref_independently(
    tmp_path: Path,
    expected_revision: int,
    expected_ref: str,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "cas-parts.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    key = initial.key
    first_job, worker, attempt = _create_action_job(store, job_id="action-advance")
    advanced = _append_action(
        store,
        job=first_job,
        worker_id=worker,
        attempt=attempt,
        key=key,
        expected_revision=1,
        expected_ref=initial.frontier_ref,
        route_id="route-advance",
        replacement=_value("compiled-b", "selected-tuple-b"),
    )
    assert advanced.frontier.revision == 2

    second_job, worker2, attempt2 = _create_action_job(store, job_id="action-stale")
    stale_revision, stale_ref = (
        (expected_revision, expected_ref) if expected_revision == 1 else (2, initial.frontier_ref)
    )
    with pytest.raises(ValueError, match="frontier_conflict"):
        _append_action(
            store,
            job=second_job,
            worker_id=worker2,
            attempt=attempt2,
            key=key,
            expected_revision=stale_revision,
            expected_ref=stale_ref,
            route_id=f"route-stale-{expected_revision}",
            replacement=None,
        )
    assert store.read_acquisition_evaluation_frontier(key) == advanced.frontier


def test_sibling_retained_terminals_serialize_without_advancing_frontier(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "concurrent-retained.sqlite3"
    stores = tuple(ControlPlaneStore(backend="sqlite", sqlite_path=sqlite_path) for _ in range(2))
    _, initial, _ = _bootstrap(stores[0], tmp_path)
    key = initial.key
    jobs = tuple(_create_action_job(stores[0], job_id=f"action-{index}") for index in range(2))
    barrier = threading.Barrier(2)

    def append(index: int) -> Any:
        job, worker, attempt = jobs[index]
        barrier.wait(timeout=10)
        with stores[index].job_execution_fence(
            job_id=job.job_id, worker_id=worker, attempt=attempt
        ):
            return stores[index].advance_acquisition_action_head_with_frontier(
                tenant_id=key.tenant_id,
                cell_id=key.cell_id,
                run_id="run-a",
                source_job_id=key.source_job_id,
                route_id=_sha(f"route-{index}"),
                action_generation=1,
                expected_head_generation=0,
                receipt_ref=_sha(f"receipt-{index}"),
                receipt_sha256=_sha(f"receipt-{index}"),
                durable_event_id=f"event-{index}",
                coarse_phase="completed",
                receipt_phase="completed",
                recovery_state="none",
                job_id=job.job_id,
                predecessor_receipt_ref=None,
                frontier_cas=_types()[2](
                    key=key,
                    expected_revision=1,
                    expected_frontier_ref=initial.frontier_ref,
                    replacement=None,
                ),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        commits = tuple(pool.map(append, range(2)))
    assert len({commit.head.route_id for commit in commits}) == 2
    assert all(commit.frontier == initial for commit in commits)
    assert stores[0].read_acquisition_evaluation_frontier(key) == initial


def test_bootstrap_requires_live_source_worker_fence(tmp_path: Path) -> None:
    _, _, cas_type = _types()
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "unfenced.sqlite3")
    job = _create_job(store, job_id="source-nl", kind="natural_language_run", run_id="run-a")
    value = _value()
    compiled_id = value.selected_evaluation_witness_ref
    cas = cas_type(
        key=_key(),
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=value,
    )
    progress = {
        "compiled_recursive_generation_cycle_ref": compiled_id,
        "compiled_recursive_generation_cycle_artifact_ref": {
            "artifact_id": compiled_id,
            "kind": "runtime.compiled_recursive_generation_cycle",
            "media_type": "application/json",
        },
    }
    with pytest.raises(ControlJobLeaseLostError, match="requires_current_job_fence"):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress=progress,
            selected_evaluation_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "pending"
    assert store.read_acquisition_evaluation_frontier(_key()) is None


def test_bootstrap_requires_the_admitted_tenant_and_cell_scope(tmp_path: Path) -> None:
    _, _, cas_type = _types()
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "wrong-scope.sqlite3")
    job = _create_job(store, job_id="source-nl", kind="natural_language_run", run_id="run-a")
    worker_id, attempt = _lease_job(store, job, "worker-source")
    value = _value()
    compiled_id = value.selected_evaluation_witness_ref
    wrong_key = _types()[0](
        tenant_id="tenant-other",
        cell_id="cell-a",
        source_job_id=job.job_id,
        design_problem_ref=_sha("design"),
        candidate_id="candidate-a",
    )
    cas = cas_type(
        key=wrong_key,
        expected_revision=0,
        expected_frontier_ref=None,
        replacement=value,
    )
    progress = {
        "compiled_recursive_generation_cycle_ref": compiled_id,
        "compiled_recursive_generation_cycle_artifact_ref": {
            "artifact_id": compiled_id,
            "kind": "runtime.compiled_recursive_generation_cycle",
            "media_type": "application/json",
        },
    }
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt),
        pytest.raises(store_module.ControlJobExecutionAdmissionError, match="scope_mismatch"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress=progress,
            selected_evaluation_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "running"
    assert store.read_acquisition_evaluation_frontier(wrong_key) is None


# V3 transaction-relation oracles: assert public readback after real SQL changes.
def _oracle_frontier_ref(key: Any, revision: int, value: Any) -> str:
    # Independent encoding of the versioned selector payload, not the store helper.
    payload = {
        "schema_version": "polisyos.control.acquisition_evaluation_frontier.v1",
        "tenant_id": key.tenant_id,
        "cell_id": key.cell_id,
        "source_job_id": key.source_job_id,
        "design_problem_ref": key.design_problem_ref,
        "candidate_id": key.candidate_id,
        "revision": revision,
        "selected_evaluation_witness_ref": value.selected_evaluation_witness_ref,
        "selected_evaluation_content_hash": value.selected_evaluation_content_hash,
        "basis_ref": value.basis_ref,
        "basis_content_hash": value.basis_content_hash,
        "decision_ref": value.decision_ref,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _oracle_action_scope(key: Any, route: str) -> dict[str, Any]:
    return {
        "tenant_id": key.tenant_id,
        "cell_id": key.cell_id,
        "run_id": "run-a",
        "source_job_id": key.source_job_id,
        "route_id": _sha(route),
        "action_generation": 1,
    }


def _oracle_write(
    store: ControlPlaneStore,
    job: ControlJobRecord,
    initial: Any,
    *,
    route: str,
    replacement: Any,
    expected_head_generation: int = 0,
    predecessor_receipt_ref: str | None = None,
    receipt_ref: str | None = None,
    receipt_manifest_profile_sha256: str | None = None,
) -> Any:
    # Caller binds the job fence, so expiry can be injected after fence admission.
    selected_receipt_ref = receipt_ref or _sha(f"{route}:receipt:{expected_head_generation}")
    return store.advance_acquisition_action_head_with_frontier(
        **_oracle_action_scope(initial.key, route),
        expected_head_generation=expected_head_generation,
        receipt_ref=selected_receipt_ref,
        receipt_sha256=selected_receipt_ref,
        durable_event_id=f"event-{route}-{expected_head_generation}",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=job.job_id,
        predecessor_receipt_ref=predecessor_receipt_ref,
        receipt_manifest_profile_sha256=receipt_manifest_profile_sha256,
        frontier_cas=_types()[2](
            key=initial.key,
            expected_revision=initial.revision,
            expected_frontier_ref=initial.frontier_ref,
            replacement=replacement,
        ),
    )


@pytest.mark.parametrize("replace_frontier", [False, True])
def test_v3_action_relation_survives_all_readers_and_store_reopen(
    tmp_path: Path, replace_frontier: bool
) -> None:
    path = tmp_path / "v3-relation.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-relation-action")
    replacement = _value("compiled-v3", "selected-v3") if replace_frontier else None
    selected_receipt = _selected_receipt_ref(tmp_path, "selected")
    assert selected_receipt.manifest_profile_sha256 is not None
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        commit = _oracle_write(
            store,
            job,
            initial,
            route="v3-relation",
            replacement=replacement,
            receipt_ref=str(selected_receipt.artifact_id),
            receipt_manifest_profile_sha256=selected_receipt.manifest_profile_sha256,
        )
    expected_ref = (
        _oracle_frontier_ref(initial.key, 2, replacement)
        if replacement is not None
        else initial.frontier_ref
    )
    assert commit.head.evaluation_frontier_before_ref == initial.frontier_ref
    assert commit.head.evaluation_frontier_ref == expected_ref == commit.frontier.frontier_ref
    assert commit.head.receipt_ref == str(selected_receipt.artifact_id)
    assert commit.head.receipt_manifest_profile_sha256 == selected_receipt.manifest_profile_sha256
    assert commit.frontier.revision == (2 if replace_frontier else 1)
    assert commit.frontier.selected_evaluation_witness_ref == (
        replacement.selected_evaluation_witness_ref
        if replacement is not None
        else initial.selected_evaluation_witness_ref
    )
    assert commit.frontier.selected_evaluation_content_hash == (
        replacement.selected_evaluation_content_hash
        if replacement is not None
        else initial.selected_evaluation_content_hash
    )
    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    scope = _oracle_action_scope(initial.key, "v3-relation")
    assert reopened.get_acquisition_action_head(**scope) == commit.head
    assert (
        reopened.get_acquisition_action_head_by_receipt(
            **scope, receipt_ref=commit.head.receipt_ref
        )
        == commit.head
    )
    route_scope = {key: value for key, value in scope.items() if key != "action_generation"}
    assert reopened.list_acquisition_action_heads(**route_scope) == (commit.head,)
    source_scope = {key: value for key, value in route_scope.items() if key != "route_id"}
    assert reopened.list_acquisition_action_heads_for_source(**source_scope) == (commit.head,)
    assert reopened.get_acquisition_evaluation_frontier_by_ref(initial.frontier_ref) == initial
    assert reopened.get_acquisition_evaluation_frontier_by_ref(expected_ref) == commit.frontier
    assert reopened.read_acquisition_evaluation_frontier(initial.key) == commit.frontier


def test_v3_predecessor_conflict_rolls_back_frontier_version_and_relation(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "v3-predecessor.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-predecessor-action")
    selected_receipt = _selected_receipt_ref(tmp_path, "first")
    rejected_receipt = _selected_receipt_ref(tmp_path, "conflicting", version="4")
    assert selected_receipt.manifest_profile_sha256 is not None
    assert rejected_receipt.manifest_profile_sha256 is not None
    assert selected_receipt.manifest_profile_sha256 != rejected_receipt.manifest_profile_sha256
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        first = _oracle_write(
            store,
            job,
            initial,
            route="v3-same-route",
            replacement=None,
            receipt_ref=str(selected_receipt.artifact_id),
            receipt_manifest_profile_sha256=selected_receipt.manifest_profile_sha256,
        )
    replacement = _value("compiled-uncommitted", "selected-uncommitted")
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="acquisition_action_predecessor_conflict"),
    ):
        # CAS is attempted first, then the already-present route head rejects this append.
        _oracle_write(
            store,
            job,
            initial,
            route="v3-same-route",
            replacement=replacement,
            receipt_ref=str(rejected_receipt.artifact_id),
            receipt_manifest_profile_sha256=rejected_receipt.manifest_profile_sha256,
        )
    assert store.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        store.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )
    assert (
        store.get_acquisition_action_head(**_oracle_action_scope(initial.key, "v3-same-route"))
        == first.head
    )
    assert first.head.receipt_manifest_profile_sha256 == selected_receipt.manifest_profile_sha256
    assert (
        store.get_acquisition_action_head_by_receipt(
            **_oracle_action_scope(initial.key, "v3-same-route"),
            receipt_ref=str(rejected_receipt.artifact_id),
        )
        is None
    )


@pytest.mark.parametrize("replace_frontier", [False, True])
def test_exact_profiled_retry_preserves_the_committed_head_and_frontier(
    tmp_path: Path, replace_frontier: bool
) -> None:
    path = tmp_path / "profile-exact-retry.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-exact-retry-action")
    selected = _selected_receipt_ref(tmp_path, "exact-retry")
    assert selected.manifest_profile_sha256 is not None
    replacement = _value("compiled-exact", "tuple-exact") if replace_frontier else None
    args = {
        "route": "profile-exact-retry",
        "replacement": replacement,
        "receipt_ref": str(selected.artifact_id),
        "receipt_manifest_profile_sha256": selected.manifest_profile_sha256,
    }
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        first = _oracle_write(store, job, initial, **args)
    expected_error = (
        "acquisition_evaluation_frontier_conflict"
        if replace_frontier
        else "acquisition_action_predecessor_conflict"
    )
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match=expected_error),
    ):
        _oracle_write(store, job, initial, **args)

    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    scope = _oracle_action_scope(initial.key, "profile-exact-retry")
    assert first.head.receipt_ref == str(selected.artifact_id)
    assert first.head.receipt_manifest_profile_sha256 == selected.manifest_profile_sha256
    assert reopened.get_acquisition_action_head(**scope) == first.head
    assert (
        reopened.get_acquisition_action_head_by_receipt(
            **scope, receipt_ref=str(selected.artifact_id)
        )
        == first.head
    )
    route_scope = {key: value for key, value in scope.items() if key != "action_generation"}
    assert reopened.list_acquisition_action_heads(**route_scope) == (first.head,)
    assert reopened.read_acquisition_evaluation_frontier(initial.key) == first.frontier
    assert (
        reopened.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, first.frontier.revision + 1, first.frontier)
        )
        is None
    )


def test_profiled_head_refuses_same_body_other_view_and_null_downgrade(tmp_path: Path) -> None:
    path = tmp_path / "profile-identity.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-identity-action")
    selected = _selected_receipt_ref(tmp_path, "same-body", version="3")
    other_view = _selected_receipt_ref(tmp_path, "same-body", version="4")
    assert selected.artifact_id == other_view.artifact_id
    assert selected.manifest_profile_sha256 is not None
    assert other_view.manifest_profile_sha256 is not None
    assert selected.manifest_profile_sha256 != other_view.manifest_profile_sha256
    scope = _oracle_action_scope(initial.key, "profile-identity")
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        first = _oracle_write(
            store,
            job,
            initial,
            route="profile-identity",
            replacement=None,
            receipt_ref=str(selected.artifact_id),
            receipt_manifest_profile_sha256=selected.manifest_profile_sha256,
        )

    replacement = _value("compiled-profile-rejected", "tuple-profile-rejected")
    for supplied_ref, supplied_profile, expected_generation, predecessor, error in (
        (
            str(other_view.artifact_id),
            other_view.manifest_profile_sha256,
            0,
            None,
            "acquisition_action_predecessor_conflict",
        ),
        (
            str(other_view.artifact_id),
            other_view.manifest_profile_sha256,
            1,
            first.head.receipt_ref,
            "acquisition_action_receipt_manifest_profile_conflict",
        ),
        (
            str(selected.artifact_id),
            selected.manifest_profile_sha256,
            1,
            first.head.receipt_ref,
            "acquisition_action_receipt_duplicate",
        ),
        (
            _sha("another-receipt"),
            None,
            1,
            first.head.receipt_ref,
            "acquisition_action_receipt_manifest_profile_downgrade",
        ),
    ):
        with (
            store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
            pytest.raises(ValueError, match=error),
        ):
            _oracle_write(
                store,
                job,
                initial,
                route="profile-identity",
                replacement=replacement,
                expected_head_generation=expected_generation,
                predecessor_receipt_ref=predecessor,
                receipt_ref=supplied_ref,
                receipt_manifest_profile_sha256=supplied_profile,
            )
        reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
        assert reopened.get_acquisition_action_head(**scope) == first.head
        assert (
            reopened.get_acquisition_action_head_by_receipt(
                **scope, receipt_ref=str(selected.artifact_id)
            )
            == first.head
        )
        assert reopened.read_acquisition_evaluation_frontier(initial.key) == initial
        assert (
            reopened.get_acquisition_evaluation_frontier_by_ref(
                _oracle_frontier_ref(initial.key, 2, replacement)
            )
            is None
        )


def test_legacy_null_head_is_not_rebound_to_later_selected_view(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "profile-legacy.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-legacy-action")
    selected = _selected_receipt_ref(tmp_path, "legacy-body")
    assert selected.manifest_profile_sha256 is not None
    scope = _oracle_action_scope(initial.key, "profile-legacy")
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        legacy = _oracle_write(
            store,
            job,
            initial,
            route="profile-legacy",
            replacement=None,
            receipt_ref=str(selected.artifact_id),
        )
    assert legacy.head.receipt_manifest_profile_sha256 is None
    replacement = _value("compiled-legacy-rejected", "tuple-legacy-rejected")
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="acquisition_action_receipt_manifest_profile_conflict"),
    ):
        _oracle_write(
            store,
            job,
            initial,
            route="profile-legacy",
            replacement=replacement,
            expected_head_generation=1,
            predecessor_receipt_ref=legacy.head.receipt_ref,
            receipt_ref=str(selected.artifact_id),
            receipt_manifest_profile_sha256=selected.manifest_profile_sha256,
        )
    assert store.get_acquisition_action_head(**scope) == legacy.head
    assert store.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        store.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )


@pytest.mark.parametrize(
    "bad_profile", ["", "sha256:" + "a" * 63, "sha256:" + "A" * 64, "a" * 64, False]
)
def test_malformed_profile_refuses_without_head_or_frontier_write(
    tmp_path: Path, bad_profile: Any
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "profile-invalid.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-invalid-action")
    replacement = _value("compiled-invalid-profile", "tuple-invalid-profile")
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="acquisition_action_receipt_manifest_profile_invalid"),
    ):
        _oracle_write(
            store,
            job,
            initial,
            route="profile-invalid",
            replacement=replacement,
            receipt_manifest_profile_sha256=bad_profile,
        )
    assert (
        store.get_acquisition_action_head(**_oracle_action_scope(initial.key, "profile-invalid"))
        is None
    )
    assert store.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        store.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )


def test_corrupt_profile_is_refused_by_each_head_reader(tmp_path: Path) -> None:
    path = tmp_path / "profile-corrupt.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-corrupt-action")
    selected = _selected_receipt_ref(tmp_path, "profile-corrupt")
    assert selected.manifest_profile_sha256 is not None
    scope = _oracle_action_scope(initial.key, "profile-corrupt")
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        head = _oracle_write(
            store,
            job,
            initial,
            route="profile-corrupt",
            replacement=None,
            receipt_ref=str(selected.artifact_id),
            receipt_manifest_profile_sha256=selected.manifest_profile_sha256,
        ).head
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE runtime_acquisition_action_heads SET receipt_manifest_profile_sha256 = ? "
            "WHERE receipt_ref = ?",
            ("sha256:corrupt", head.receipt_ref),
        )
    route_scope = {key: value for key, value in scope.items() if key != "action_generation"}
    source_scope = {key: value for key, value in route_scope.items() if key != "route_id"}
    readers = (
        lambda: store.get_acquisition_action_head(**scope),
        lambda: store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=head.receipt_ref),
        lambda: store.list_acquisition_action_heads(**route_scope),
        lambda: store.list_acquisition_action_heads_for_source(**source_scope),
    )
    for read in readers:
        with pytest.raises(
            RuntimeError, match="acquisition_action_receipt_manifest_profile_corrupt"
        ):
            read()


@pytest.mark.parametrize("altered_field", ["receipt_ref", "receipt_manifest_profile_sha256"])
def test_head_readback_binds_receipt_and_profile_before_commit(
    tmp_path: Path, altered_field: str
) -> None:
    path = tmp_path / "profile-readback.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="profile-readback-action")
    selected = _selected_receipt_ref(tmp_path, "profile-readback")
    assert selected.manifest_profile_sha256 is not None
    replacement = _value("compiled-readback-rejected", "tuple-readback-rejected")
    statements = {
        "receipt_ref": (
            "CREATE TRIGGER change_head AFTER INSERT ON runtime_acquisition_action_heads BEGIN "
            "UPDATE runtime_acquisition_action_heads SET receipt_ref = "
            "'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee' "
            "WHERE rowid = NEW.rowid; END"
        ),
        "receipt_manifest_profile_sha256": (
            "CREATE TRIGGER change_head AFTER INSERT ON runtime_acquisition_action_heads BEGIN "
            "UPDATE runtime_acquisition_action_heads SET receipt_manifest_profile_sha256 = "
            "'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee' "
            "WHERE rowid = NEW.rowid; END"
        ),
    }
    with sqlite3.connect(path) as connection:
        connection.execute(statements[altered_field])
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(RuntimeError, match="acquisition_action_head_readback_failed"),
    ):
        _oracle_write(
            store,
            job,
            initial,
            route="profile-readback",
            replacement=replacement,
            receipt_ref=str(selected.artifact_id),
            receipt_manifest_profile_sha256=selected.manifest_profile_sha256,
        )
    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    assert (
        reopened.get_acquisition_action_head(
            **_oracle_action_scope(initial.key, "profile-readback")
        )
        is None
    )
    assert reopened.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        reopened.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )


def test_v3_sql_head_insert_abort_rolls_back_frontier_and_history(tmp_path: Path) -> None:
    path = tmp_path / "v3-insert-abort.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-abort-action")
    replacement = _value("compiled-aborted", "selected-aborted")
    selected_receipt = _selected_receipt_ref(tmp_path, "sql-abort")
    assert selected_receipt.manifest_profile_sha256 is not None
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER oracle_abort_action_insert BEFORE INSERT ON "
            "runtime_acquisition_action_heads BEGIN "
            "SELECT RAISE(ABORT, 'oracle_action_insert_abort'); END"
        )
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(sqlite3.IntegrityError, match="oracle_action_insert_abort"),
    ):
        _oracle_write(
            store,
            job,
            initial,
            route="v3-aborted",
            replacement=replacement,
            receipt_ref=str(selected_receipt.artifact_id),
            receipt_manifest_profile_sha256=selected_receipt.manifest_profile_sha256,
        )
    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    assert reopened.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        reopened.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )
    assert (
        reopened.get_acquisition_action_head(**_oracle_action_scope(initial.key, "v3-aborted"))
        is None
    )


def test_v3_expired_already_admitted_lease_cannot_write_relation(tmp_path: Path) -> None:
    path = tmp_path / "v3-expired.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-expired-action")
    fence = store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", job.job_id),
        )
    with fence, pytest.raises(ControlJobLeaseLostError):
        _oracle_write(store, job, initial, route="v3-expired", replacement=None)
    assert store.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        store.get_acquisition_action_head(**_oracle_action_scope(initial.key, "v3-expired")) is None
    )


def test_v3_same_ref_corrupt_content_is_not_a_retained_selection(tmp_path: Path) -> None:
    path = tmp_path / "v3-corrupt-content.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-corrupt-action")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE runtime_acquisition_evaluation_frontier_versions "
            "SET selected_evaluation_content_hash = ? WHERE frontier_ref = ?",
            (_sha("forged-content"), initial.frontier_ref),
        )
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(RuntimeError, match="acquisition_evaluation_frontier_record_corrupt"),
    ):
        _oracle_write(store, job, initial, route="v3-corrupt", replacement=None)
    assert (
        store.get_acquisition_action_head(**_oracle_action_scope(initial.key, "v3-corrupt")) is None
    )


def test_v3_sibling_replacements_select_one_actual_relation(tmp_path: Path) -> None:
    path = tmp_path / "v3-race.sqlite3"
    stores = tuple(ControlPlaneStore(backend="sqlite", sqlite_path=path) for _ in range(2))
    _, initial, _ = _bootstrap(stores[0], tmp_path)
    jobs = tuple(_create_action_job(stores[0], job_id=f"v3-race-{i}") for i in range(2))
    replacements = tuple(_value(f"compiled-race-{i}", f"selected-race-{i}") for i in range(2))
    barrier = threading.Barrier(2)

    def compete(index: int) -> tuple[int, Any]:
        job, worker, attempt = jobs[index]
        barrier.wait(timeout=10)
        try:
            with stores[index].job_execution_fence(
                job_id=job.job_id, worker_id=worker, attempt=attempt
            ):
                return index, _oracle_write(
                    stores[index],
                    job,
                    initial,
                    route=f"v3-race-{index}",
                    replacement=replacements[index],
                )
        except ValueError as error:
            if str(error) != "acquisition_evaluation_frontier_conflict":
                raise
            return index, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(compete, range(2)))
    winners = tuple((index, result) for index, result in outcomes if result is not None)
    assert len(winners) == 1
    winner, commit = winners[0]
    loser = 1 - winner
    assert commit.head.evaluation_frontier_before_ref == initial.frontier_ref
    assert commit.head.evaluation_frontier_ref == _oracle_frontier_ref(
        initial.key, 2, replacements[winner]
    )
    assert stores[0].read_acquisition_evaluation_frontier(initial.key) == commit.frontier

    assert (
        stores[0].get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacements[loser])
        )
        is None
    )
    assert (
        stores[0].get_acquisition_action_head(
            **_oracle_action_scope(initial.key, f"v3-race-{loser}")
        )
        is None
    )


def _generic_ref(
    tmp_path: Path, label: str, kind: str, *, media_type: str = "application/json"
) -> Any:
    cas = FileSystemCAS(tmp_path / "generic-frontier-artifacts")
    options = ArtifactWriteOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name="polisyos.test.generic_frontier", version="1"),
    )
    if media_type == "application/json":
        return cas.put_json({"label": label, "kind": kind}, options, return_selected_profile=True)
    return cas.put_bytes(
        json.dumps({"label": label, "kind": kind}, sort_keys=True).encode("utf-8"),
        options,
        return_selected_profile=True,
    )


def _generic_persist_record(tmp_path: Path, record: Any) -> Any:
    return FileSystemCAS(tmp_path / "generic-frontier-artifacts").put_json(
        record.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=record.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=record.ARTIFACT_SCHEMA_NAME, version="1.0"),
        ),
        return_selected_profile=True,
    )


def _generic_model_input_key(source_job_id: str = "source-nl") -> Any:
    key_type = store_module.GenericModelInputEvaluationFrontierKey
    return key_type(
        tenant_id="tenant-a",
        cell_id="cell-a",
        source_job_id=source_job_id,
        design_problem_ref=_sha("design"),
        candidate_id="candidate-a",
    )


def _rehash_generic_model_record(record_type: type[Any], fields: dict[str, Any]) -> Any:
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

    provisional = record_type.model_construct(**fields, content_hash=_sha("placeholder"))
    payload = provisional.model_dump(mode="json", exclude={"content_hash"})
    return record_type.model_validate({**payload, "content_hash": exact_n5_content_hash(payload)})


def _generic_selected_evaluation(tmp_path: Path, *, action_job_id: str, suffix: str) -> Any:
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputSelectedEvaluation,
    )

    return GenericModelInputSelectedEvaluation(
        input_ref=_generic_ref(
            tmp_path, f"{suffix}-input", "runtime.quality.generic_cycle_simulation_n5_input"
        ),
        execution_ref=_generic_ref(
            tmp_path, f"{suffix}-execution", "runtime.quality.generic_cycle_simulation_n5_execution"
        ),
        result_ref=_generic_ref(
            tmp_path, f"{suffix}-result", "polisyos.runtime.joint_simulation_result"
        ),
        semantic_successor_ref=_generic_ref(
            tmp_path, f"{suffix}-successor", "runtime.quality.model_input_successor_selection"
        ),
        action_job_id=action_job_id,
    )


def _generic_basis(
    tmp_path: Path,
    *,
    source_job_id: str,
    action_job_id: str,
    selected_evaluation: Any | None,
    role: str,
    prospective_basis_ref: Any | None = None,
    comparison_decision_ref: Any | None = None,
) -> tuple[Any, Any]:
    from polisyos.runtime.quality.acquisition_evaluation import (
        CANDIDATE_N5_CLOSURE_RESIDUALS_V2,
        GenericModelInputEvaluationBasisV1,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash

    selected = selected_evaluation or _generic_selected_evaluation(
        tmp_path, action_job_id=action_job_id, suffix=f"{action_job_id}-candidate"
    )
    fields: dict[str, Any] = {
        "schema_version": "GenericModelInputEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "generic_program_graph_declared_numerical_v1",
        "basis_role": role,
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "run_id": "run-a",
        "source_job_id": source_job_id,
        "action_job_id": action_job_id,
        "route_id": _sha(f"{action_job_id}-route"),
        "design_problem_ref": _sha("design"),
        "design_problem_basis_ref": _sha(f"{action_job_id}-active-design-basis"),
        "candidate_id": "candidate-a",
        "input_ref": selected.input_ref,
        "semantic_successor_ref": selected.semantic_successor_ref,
        "bound_state_snapshot_ref": _generic_ref(
            tmp_path, f"{action_job_id}-state", "foundry.state_snapshot"
        ),
        "evaluation": selected if role == "evaluated" else None,
        "prospective_basis_ref": prospective_basis_ref,
        "comparison_decision_ref": comparison_decision_ref,
        "predicate_provenance": "recomputed",
        "reason_codes": (),
        "limitations": ("candidate_evaluation_retention_only",),
        "closure_residuals": CANDIDATE_N5_CLOSURE_RESIDUALS_V2,
        "observed_admission": False,
        "publication_authority": False,
        "numerical_intent_hex": "00",
        "numerical_intent_sha256": _sha_bytes(bytes.fromhex("00")),
    }
    payload = GenericModelInputEvaluationBasisV1.model_construct(
        **fields, content_hash=_sha("placeholder")
    ).model_dump(mode="json", exclude={"content_hash"})
    basis = GenericModelInputEvaluationBasisV1.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )
    basis_ref = _generic_persist_record(tmp_path, basis)
    return basis, basis_ref


def _generic_decision(
    tmp_path: Path,
    *,
    key: Any,
    action_job_id: str,
    current_basis: Any,
    current_basis_ref: Any,
    decision_kind: str,
    comparison_result: str | None,
    expected_revision: int,
    expected_ref: str | None,
    prior_basis_ref: Any | None = None,
    prior_evaluation: Any | None = None,
) -> tuple[Any, Any]:
    from polisyos.runtime.quality.acquisition_evaluation import (
        GenericModelInputEvaluationDecisionV1,
    )

    activation = _generic_ref(
        tmp_path,
        f"{action_job_id}-activation",
        "epoch.activated_overlay_admission_receipt",
        media_type="application/vnd.polisyos.epoch+json",
    )
    fields = {
        "schema_version": "GenericModelInputEvaluationDecision@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "generic-program-graph-declared-numerical-basis.v1",
        "decision_kind": decision_kind,
        "tenant_id": key.tenant_id,
        "cell_id": key.cell_id,
        "run_id": "run-a",
        "source_job_id": key.source_job_id,
        "action_job_id": action_job_id,
        "route_id": current_basis.route_id,
        "design_problem_ref": key.design_problem_ref,
        "design_problem_basis_ref": current_basis.design_problem_basis_ref,
        "candidate_id": key.candidate_id,
        "action_phase_ref": _generic_ref(
            tmp_path, f"{action_job_id}-phase", "runtime.quality.model_input_use_action_phase"
        ),
        "semantic_successor_ref": current_basis.semantic_successor_ref,
        "routing_use_decision_ref": _generic_ref(
            tmp_path, f"{action_job_id}-routing", "runtime.quality.model_input_routing_use_decision"
        ),
        "authority_decision_ref": _generic_ref(
            tmp_path,
            f"{action_job_id}-authority",
            "runtime_quality.agent_action_authority_decision",
        ),
        "activation_receipt_ref": activation,
        "current_basis_ref": current_basis_ref,
        "prior_basis_ref": prior_basis_ref,
        "prior_evaluation": prior_evaluation,
        "comparison_result": comparison_result,
        "predicate_provenance": (
            "not_established" if comparison_result == "not_established" else "recomputed"
        ),
        "reason_codes": (
            ("generic_model_input_prior_not_established",)
            if comparison_result == "not_established"
            else ()
        ),
        "expected_frontier_revision": expected_revision,
        "expected_frontier_ref": expected_ref,
        "observed_admission": False,
        "publication_authority": False,
        "generated_at": "2026-11-13T00:00:00+00:00",
    }
    decision = _rehash_generic_model_record(GenericModelInputEvaluationDecisionV1, fields)
    decision_ref = _generic_persist_record(tmp_path, decision)
    return decision, decision_ref


def _sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _generic_cas(
    *,
    key: Any,
    action_job_id: str,
    decision: Any,
    decision_ref: Any,
    current_basis: Any,
    replacement_basis: Any | None,
    replacement: Any,
    expected_revision: int,
    expected_ref: str | None,
) -> Any:
    cas_type = store_module.GenericModelInputEvaluationFrontierCAS
    return cas_type(
        key=key,
        expected_revision=expected_revision,
        expected_frontier_ref=expected_ref,
        action_job_id=action_job_id,
        decision_ref=decision_ref,
        decision=decision,
        current_basis=current_basis,
        replacement_basis=replacement_basis,
        replacement=replacement,
    )


def _prepare_generic_initial(
    store: ControlPlaneStore,
    tmp_path: Path,
    *,
    source_job_id: str = "source-nl",
    action_job_id: str = "generic-initial",
    create_source: bool = True,
    action_job_bundle: tuple[ControlJobRecord, str, int] | None = None,
) -> tuple[Any, ...]:
    from polisyos.runtime.http.services.control_plane_store import (
        GenericModelInputEvaluationFrontierValue,
    )

    if create_source:
        source, _, _ = _bootstrap(store, tmp_path, source_job_id=source_job_id)
    else:
        source = store.get_job(source_job_id)
        assert source is not None
    key = _generic_model_input_key(source_job_id)
    job, worker, attempt = action_job_bundle or _create_action_job(store, job_id=action_job_id)
    evaluation = _generic_selected_evaluation(
        tmp_path, action_job_id=job.job_id, suffix=f"{action_job_id}-source-v5"
    )
    basis, basis_ref = _generic_basis(
        tmp_path,
        source_job_id=source_job_id,
        action_job_id=job.job_id,
        selected_evaluation=evaluation,
        role="evaluated",
    )
    decision, decision_ref = _generic_decision(
        tmp_path,
        key=key,
        action_job_id=job.job_id,
        current_basis=basis,
        current_basis_ref=basis_ref,
        decision_kind="initial",
        comparison_result=None,
        expected_revision=0,
        expected_ref=None,
    )
    value = GenericModelInputEvaluationFrontierValue(
        basis_ref=basis_ref,
        basis_content_hash=basis.content_hash,
        selected_evaluation=evaluation,
        selection_decision_ref=decision_ref,
    )
    cas = _generic_cas(
        key=key,
        action_job_id=job.job_id,
        decision=decision,
        decision_ref=decision_ref,
        current_basis=basis,
        replacement_basis=basis,
        replacement=value,
        expected_revision=0,
        expected_ref=None,
    )
    return (
        source,
        key,
        job,
        worker,
        attempt,
        basis,
        decision,
        decision_ref,
        evaluation,
        basis_ref,
        value,
        cas,
    )


def _commit_generic_initial(
    store: ControlPlaneStore,
    tmp_path: Path,
    *,
    source_job_id: str = "source-nl",
    action_job_id: str = "generic-initial",
    create_source: bool = True,
) -> tuple[Any, Any, Any, Any, str, int, Any, Any, Any, Any, Any]:
    bundle = _prepare_generic_initial(
        store,
        tmp_path,
        source_job_id=source_job_id,
        action_job_id=action_job_id,
        create_source=create_source,
    )
    source, key, job, worker, attempt, basis, decision, decision_ref, evaluation, basis_ref = (
        bundle[:10]
    )
    cas = bundle[11]
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    record = store.read_generic_model_input_frontier(key)
    assert record is not None and record.revision == 1
    return (
        source,
        key,
        job,
        worker,
        attempt,
        basis,
        decision,
        decision_ref,
        evaluation,
        basis_ref,
        record,
    )


def _prepare_generic_comparison(
    store: ControlPlaneStore,
    tmp_path: Path,
    *,
    source_job_id: str,
    prior: Any,
    action_job_id: str,
    result: str,
    expected_revision: int | None = None,
    expected_ref: str | None = None,
    fresh_n5: bool = True,
) -> tuple[Any, str, int, Any, Any, Any, Any, Any]:
    from polisyos.runtime.http.services.control_plane_store import (
        GenericModelInputEvaluationFrontierValue,
    )

    job, worker, attempt = _create_action_job(store, job_id=action_job_id)
    evaluated = (
        _generic_selected_evaluation(
            tmp_path, action_job_id=job.job_id, suffix=f"{action_job_id}-new-v5"
        )
        if result == "different" or (result == "not_established" and fresh_n5)
        else prior.selected_evaluation
    )
    current_basis, current_basis_ref = _generic_basis(
        tmp_path,
        source_job_id=source_job_id,
        action_job_id=job.job_id,
        selected_evaluation=evaluated,
        role="prospective",
    )
    decision, decision_ref = _generic_decision(
        tmp_path,
        key=prior.key,
        action_job_id=job.job_id,
        current_basis=current_basis,
        current_basis_ref=current_basis_ref,
        decision_kind="comparison",
        comparison_result=result,
        expected_revision=prior.revision if expected_revision is None else expected_revision,
        expected_ref=prior.frontier_ref if expected_ref is None else expected_ref,
        prior_basis_ref=prior.basis_ref,
        prior_evaluation=prior.selected_evaluation,
    )
    replacement_basis = None
    replacement_basis_ref = None
    replacement = None
    if result == "different" or (result == "not_established" and fresh_n5):
        replacement_basis, replacement_basis_ref = _generic_basis(
            tmp_path,
            source_job_id=source_job_id,
            action_job_id=job.job_id,
            selected_evaluation=evaluated,
            role="evaluated",
            prospective_basis_ref=current_basis_ref,
            comparison_decision_ref=decision_ref,
        )
        replacement = GenericModelInputEvaluationFrontierValue(
            basis_ref=replacement_basis_ref,
            basis_content_hash=replacement_basis.content_hash,
            selected_evaluation=evaluated,
            selection_decision_ref=decision_ref,
        )
    cas = _generic_cas(
        key=prior.key,
        action_job_id=job.job_id,
        decision=decision,
        decision_ref=decision_ref,
        current_basis=current_basis,
        replacement_basis=replacement_basis,
        replacement=replacement,
        expected_revision=prior.revision if expected_revision is None else expected_revision,
        expected_ref=prior.frontier_ref if expected_ref is None else expected_ref,
    )
    return job, worker, attempt, current_basis, decision, decision_ref, replacement_basis, cas


def test_generic_frontier_initial_check_only_and_changed_subject_share_cas_key(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control_plane_store import (
        GenericModelInputEvaluationFrontierValue,
    )

    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "generic-use.sqlite3")
    (
        source,
        key,
        initial_job,
        _,
        _,
        _,
        _,
        _,
        initial_eval,
        _,
        initial,
    ) = _commit_generic_initial(store, tmp_path)
    legacy_initial = store.read_acquisition_evaluation_frontier(_key(source.job_id))
    assert legacy_initial is not None
    assert (
        key.tenant_id,
        key.cell_id,
        key.source_job_id,
        key.design_problem_ref,
        key.candidate_id,
    ) == (
        legacy_initial.key.tenant_id,
        legacy_initial.key.cell_id,
        legacy_initial.key.source_job_id,
        legacy_initial.key.design_problem_ref,
        legacy_initial.key.candidate_id,
    )
    assert key.family == "generic_program_graph"
    assert initial.selected_evaluation == initial_eval
    initial_checkpoint = store.get_job(initial_job.job_id)
    assert initial_checkpoint is not None
    assert initial_checkpoint.progress["generic_model_input_current_use"]["frontier_ref"] == (
        initial.frontier_ref
    )
    initial_terminal = store.get_job_terminal_source_event_record(initial_job.job_id)
    assert initial_terminal.payload["generic_model_input_current_use"]["frontier_ref"] == (
        initial.frontier_ref
    )

    repeated_job, repeated_worker, repeated_attempt = _create_action_job(
        store, job_id="generic-equivalent"
    )
    repeated_basis, repeated_basis_ref = _generic_basis(
        tmp_path,
        source_job_id=source.job_id,
        action_job_id=repeated_job.job_id,
        selected_evaluation=initial_eval,
        role="prospective",
    )
    equivalent_decision, equivalent_decision_ref = _generic_decision(
        tmp_path,
        key=key,
        action_job_id=repeated_job.job_id,
        current_basis=repeated_basis,
        current_basis_ref=repeated_basis_ref,
        decision_kind="comparison",
        comparison_result="equivalent",
        expected_revision=initial.revision,
        expected_ref=initial.frontier_ref,
        prior_basis_ref=initial.basis_ref,
        prior_evaluation=initial.selected_evaluation,
    )
    with store.job_execution_fence(
        job_id=repeated_job.job_id, worker_id=repeated_worker, attempt=repeated_attempt
    ):
        store.complete_job(
            job_id=repeated_job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=_generic_cas(
                key=key,
                action_job_id=repeated_job.job_id,
                decision=equivalent_decision,
                decision_ref=equivalent_decision_ref,
                current_basis=repeated_basis,
                replacement_basis=None,
                replacement=None,
                expected_revision=initial.revision,
                expected_ref=initial.frontier_ref,
            ),
        )
    equivalent_use = store.get_generic_model_input_use(key=key, action_job_id=repeated_job.job_id)
    assert equivalent_use is not None
    assert equivalent_use.frontier_ref == initial.frontier_ref
    assert equivalent_use.decision_ref == equivalent_decision_ref
    assert store.read_generic_model_input_frontier(key) == initial

    changed_job, changed_worker, changed_attempt = _create_action_job(
        store, job_id="generic-changed"
    )
    changed_eval = _generic_selected_evaluation(
        tmp_path, action_job_id=changed_job.job_id, suffix="generic-new-current-v5"
    )
    changed_basis, changed_basis_ref = _generic_basis(
        tmp_path,
        source_job_id=source.job_id,
        action_job_id=changed_job.job_id,
        selected_evaluation=changed_eval,
        role="prospective",
    )
    changed_decision, changed_decision_ref = _generic_decision(
        tmp_path,
        key=key,
        action_job_id=changed_job.job_id,
        current_basis=changed_basis,
        current_basis_ref=changed_basis_ref,
        decision_kind="comparison",
        comparison_result="different",
        expected_revision=initial.revision,
        expected_ref=initial.frontier_ref,
        prior_basis_ref=initial.basis_ref,
        prior_evaluation=initial.selected_evaluation,
    )
    replacement_basis, replacement_basis_ref = _generic_basis(
        tmp_path,
        source_job_id=source.job_id,
        action_job_id=changed_job.job_id,
        selected_evaluation=changed_eval,
        role="evaluated",
        prospective_basis_ref=changed_basis_ref,
        comparison_decision_ref=changed_decision_ref,
    )
    changed_value = GenericModelInputEvaluationFrontierValue(
        basis_ref=replacement_basis_ref,
        basis_content_hash=replacement_basis.content_hash,
        selected_evaluation=changed_eval,
        selection_decision_ref=changed_decision_ref,
    )
    with store.job_execution_fence(
        job_id=changed_job.job_id, worker_id=changed_worker, attempt=changed_attempt
    ):
        store.complete_job(
            job_id=changed_job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=_generic_cas(
                key=key,
                action_job_id=changed_job.job_id,
                decision=changed_decision,
                decision_ref=changed_decision_ref,
                current_basis=changed_basis,
                replacement_basis=replacement_basis,
                replacement=changed_value,
                expected_revision=initial.revision,
                expected_ref=initial.frontier_ref,
            ),
        )
    current = store.read_generic_model_input_frontier(key)
    assert current is not None and current.revision == 2
    assert current.key == initial.key
    assert current.selected_evaluation == changed_eval
    assert current.frontier_ref != initial.frontier_ref
    assert store.get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    assert store.read_acquisition_evaluation_frontier(_key(source.job_id)) == legacy_initial
    changed_checkpoint = store.get_job(changed_job.job_id)
    assert changed_checkpoint is not None
    assert changed_checkpoint.progress["generic_model_input_current_use"]["frontier_ref"] == (
        current.frontier_ref
    )
    changed_terminal = store.get_job_terminal_source_event_record(changed_job.job_id)
    assert changed_terminal.payload["generic_model_input_current_use"]["frontier_ref"] == (
        current.frontier_ref
    )


@pytest.mark.parametrize("stale_part", ["revision", "ref"])
def test_generic_frontier_stale_revision_or_ref_rolls_back_completion(
    tmp_path: Path,
    stale_part: str,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "generic-stale.sqlite3")
    source, _, _, _, _, _, _, _, _, _, initial = _commit_generic_initial(store, tmp_path)
    wrong_revision = initial.revision + 1 if stale_part == "revision" else initial.revision
    wrong_ref = _sha("stale-generic-frontier") if stale_part == "ref" else initial.frontier_ref
    job, worker, attempt, _, _, _, _, cas = _prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id=f"generic-stale-{stale_part}",
        result="equivalent",
        expected_revision=wrong_revision,
        expected_ref=wrong_ref,
    )
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="generic_model_input_frontier_conflict"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "running"
    assert store.read_generic_model_input_frontier(initial.key) == initial
    assert store.get_generic_model_input_use(key=initial.key, action_job_id=job.job_id) is None


def test_generic_frontier_wrong_action_and_wrong_source_fail_closed(tmp_path: Path) -> None:
    store = ControlPlaneStore(
        backend="sqlite", sqlite_path=tmp_path / "generic-wrong-owner.sqlite3"
    )
    _bootstrap(store, tmp_path)
    _, key, job, _, _, _, _, _, _, _, _, cas = _prepare_generic_initial(
        store,
        tmp_path,
        action_job_id="generic-wrong-action-binding",
        create_source=False,
    )
    other_job, other_worker, other_attempt = _create_action_job(
        store, job_id="generic-other-current-action"
    )
    with (
        store.job_execution_fence(
            job_id=other_job.job_id,
            worker_id=other_worker,
            attempt=other_attempt,
        ),
        pytest.raises(ValueError, match="generic_model_input_frontier_action_job_mismatch"),
    ):
        store.complete_job(
            job_id=other_job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    assert store.get_job(job.job_id).state == "running"
    assert store.get_job(other_job.job_id).state == "running"
    assert store.read_generic_model_input_frontier(key) is None

    source_action_bundle = _create_action_job(store, job_id="generic-wrong-source")
    missing_source = _create_job(
        store, job_id="generic-unverified-source", kind="natural_language_run", run_id="run-a"
    )
    _, source_key, source_action, source_worker, source_attempt, _, _, _, _, _, _, source_cas = (
        _prepare_generic_initial(
            store,
            tmp_path,
            source_job_id=missing_source.job_id,
            action_job_id="generic-wrong-source",
            create_source=False,
            action_job_bundle=source_action_bundle,
        )
    )
    with (
        store.job_execution_fence(
            job_id=source_action.job_id,
            worker_id=source_worker,
            attempt=source_attempt,
        ),
        pytest.raises(
            store_module.ControlJobExecutionAdmissionError,
            match="source_scope_not_established",
        ),
    ):
        store.complete_job(
            job_id=source_action.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=source_cas,
        )
    assert store.get_job(missing_source.job_id).state == "pending"
    assert store.get_job(source_action.job_id).state == "running"
    assert store.read_generic_model_input_frontier(source_key) is None


def test_generic_frontier_lost_lease_cannot_commit_use_or_selection(tmp_path: Path) -> None:
    path = tmp_path / "generic-lost-lease.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    source, _, _, _, _, _, _, _, _, _, initial = _commit_generic_initial(store, tmp_path)
    job, worker, attempt, _, _, _, _, cas = _prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id="generic-expired-lease",
        result="equivalent",
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", job.job_id),
        )
    with (
        pytest.raises(ControlJobLeaseLostError),
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    assert store.read_generic_model_input_frontier(initial.key) == initial
    assert store.get_generic_model_input_use(key=initial.key, action_job_id=job.job_id) is None
    assert store.get_job(job.job_id).state == "running"


def test_generic_frontier_unknown_comparison_does_not_advance_without_fresh_n5(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "generic-unknown.sqlite3")
    source, _, _, _, _, _, _, _, _, _, initial = _commit_generic_initial(store, tmp_path)
    job, worker, attempt, _, decision, _, _, cas = _prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id="generic-unknown-prior",
        result="not_established",
        fresh_n5=False,
    )
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    assert decision.comparison_result == "not_established"
    assert store.read_generic_model_input_frontier(initial.key) == initial
    use = store.get_generic_model_input_use(key=initial.key, action_job_id=job.job_id)
    assert use is not None
    assert use.comparison_result == "not_established"
    assert use.frontier_ref == initial.frontier_ref


def test_generic_frontier_not_established_comparison_advances_only_with_evaluated_basis(
    tmp_path: Path,
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "generic-ne-n5.sqlite3")
    source, _, _, _, _, _, _, _, _, _, initial = _commit_generic_initial(store, tmp_path)
    job, worker, attempt, _, decision, _, replacement_basis, cas = _prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id="generic-ne-with-new-n5",
        result="not_established",
        fresh_n5=True,
    )
    assert decision.comparison_result == "not_established"
    assert replacement_basis is not None and replacement_basis.basis_role == "evaluated"
    assert replacement_basis.predicate_provenance == "recomputed"
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    current = store.read_generic_model_input_frontier(initial.key)
    assert current is not None and current.revision == initial.revision + 1
    assert current.selected_evaluation.action_job_id == job.job_id
    assert store.get_generic_model_input_frontier_by_ref(initial.frontier_ref) == initial
    use = store.get_generic_model_input_use(key=initial.key, action_job_id=job.job_id)
    assert use is not None
    assert use.comparison_result == "not_established"
    assert use.frontier_ref == current.frontier_ref


def test_generic_frontier_post_n5_replacement_and_use_rollback_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "generic-crash.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    source, _, _, _, _, _, _, _, _, _, initial = _commit_generic_initial(store, tmp_path)
    job, worker, attempt, _, _, _, _, cas = _prepare_generic_comparison(
        store,
        tmp_path,
        source_job_id=source.job_id,
        prior=initial,
        action_job_id="generic-post-n5-crash",
        result="different",
    )
    execute = store._execute

    def fail_at_use_insert(sql: str, params: tuple[Any, ...]) -> int:
        if "INSERT INTO runtime_generic_model_input_evaluation_uses" in sql:
            raise RuntimeError("generic_use_insert_interrupted")
        return execute(sql, params)

    monkeypatch.setattr(store, "_execute", fail_at_use_insert)
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(RuntimeError, match="generic_use_insert_interrupted"),
    ):
        store.complete_job(
            job_id=job.job_id,
            run_id="run-a",
            progress={},
            generic_model_input_frontier_cas=cas,
        )
    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    assert reopened.read_generic_model_input_frontier(initial.key) == initial
    assert reopened.get_generic_model_input_use(key=initial.key, action_job_id=job.job_id) is None
    assert reopened.get_job(job.job_id).state == "running"


def test_v3_legacy_schema_upgrade_preserves_null_unproven_relation(tmp_path: Path) -> None:
    path = tmp_path / "v3-legacy-upgrade.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE runtime_acquisition_action_heads ("
            "tenant_id TEXT NOT NULL, cell_id TEXT NOT NULL, run_id TEXT NOT NULL, "
            "source_job_id TEXT NOT NULL, route_id TEXT NOT NULL, "
            "action_generation INTEGER NOT NULL, head_generation INTEGER NOT NULL, "
            "receipt_ref TEXT NOT NULL, receipt_sha256 TEXT NOT NULL, "
            "durable_event_id TEXT NOT NULL, coarse_phase TEXT NOT NULL, "
            "receipt_phase TEXT NOT NULL, recovery_state TEXT NOT NULL, job_id TEXT NOT NULL, "
            "predecessor_receipt_ref TEXT, created_at TEXT NOT NULL, "
            "PRIMARY KEY (tenant_id, cell_id, run_id, source_job_id, route_id, "
            "action_generation, head_generation))"
        )
        connection.execute(
            "INSERT INTO runtime_acquisition_action_heads VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tenant-a",
                "cell-a",
                "run-a",
                "source-nl",
                _sha("legacy-route"),
                1,
                1,
                _sha("legacy-receipt"),
                _sha("legacy-receipt"),
                "legacy-event",
                "terminal",
                "terminal",
                "complete",
                "legacy-job",
                None,
                "2026-01-01T00:00:00+00:00",
            ),
        )
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    scope = _oracle_action_scope(_key(), "legacy-route")
    legacy = store.get_acquisition_action_head(**scope)
    assert legacy is not None
    assert legacy.receipt_manifest_profile_sha256 is None
    assert legacy.evaluation_frontier_before_ref is None
    assert legacy.evaluation_frontier_ref is None
    assert (
        store.get_acquisition_action_head_by_receipt(**scope, receipt_ref=_sha("legacy-receipt"))
        == legacy
    )
    # A legacy append through the new writer is also unproven, even with terminal markers.
    added = store.advance_acquisition_action_head(
        **{**scope, "route_id": _sha("legacy-new-route")},
        expected_head_generation=0,
        receipt_ref=_sha("legacy-new-receipt"),
        receipt_sha256=_sha("legacy-new-receipt"),
        durable_event_id="legacy-new-event",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id="legacy-new-job",
        predecessor_receipt_ref=None,
    )
    assert added.evaluation_frontier_before_ref is None
    assert added.evaluation_frontier_ref is None
    assert added.receipt_manifest_profile_sha256 is None


@pytest.mark.parametrize("stale_part", ["revision", "selected_ref"])
def test_v3_mismatched_frontier_condition_cannot_persist_relation(
    tmp_path: Path, stale_part: str
) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "v3-mismatch.sqlite3")
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-mismatch-action")
    replacement = _value("compiled-never-selected", "selected-never-selected")
    with pytest.raises(ValueError, match="acquisition_evaluation_frontier_conflict"):
        _append_action(
            store,
            job=job,
            worker_id=worker,
            attempt=attempt,
            key=initial.key,
            expected_revision=initial.revision + (stale_part == "revision"),
            expected_ref=_sha("unselected-ref")
            if stale_part == "selected_ref"
            else initial.frontier_ref,
            route_id="v3-mismatch",
            replacement=replacement,
        )
    assert store.read_acquisition_evaluation_frontier(initial.key) == initial
    assert (
        store.get_acquisition_evaluation_frontier_by_ref(
            _oracle_frontier_ref(initial.key, 2, replacement)
        )
        is None
    )
    assert (
        store.get_acquisition_action_head(**_oracle_action_scope(initial.key, "v3-mismatch"))
        is None
    )
