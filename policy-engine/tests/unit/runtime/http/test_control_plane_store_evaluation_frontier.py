from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest

import polisyos.runtime.http.services.control_plane_store as store_module
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
) -> Any:
    _, _, cas_type = _types()
    cas = cas_type(
        key=key,
        expected_revision=expected_revision,
        expected_frontier_ref=expected_ref,
        replacement=replacement,
    )
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker_id, attempt=attempt):
        return store.advance_acquisition_action_head_with_frontier(
            tenant_id=key.tenant_id,
            cell_id=key.cell_id,
            run_id="run-a",
            source_job_id=key.source_job_id,
            route_id=_sha(route_id),
            action_generation=1,
            expected_head_generation=0,
            receipt_ref=_sha(f"{route_id}:receipt"),
            receipt_sha256=_sha(f"{route_id}:receipt"),
            durable_event_id=f"event-{route_id}",
            coarse_phase="completed",
            receipt_phase="completed",
            recovery_state="none",
            job_id=job.job_id,
            predecessor_receipt_ref=None,
            frontier_cas=cas,
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
