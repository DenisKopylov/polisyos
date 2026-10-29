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
) -> Any:
    # Caller binds the job fence, so expiry can be injected after fence admission.
    return store.advance_acquisition_action_head_with_frontier(
        **_oracle_action_scope(initial.key, route),
        expected_head_generation=expected_head_generation,
        receipt_ref=_sha(f"{route}:receipt:{expected_head_generation}"),
        receipt_sha256=_sha(f"{route}:receipt:{expected_head_generation}"),
        durable_event_id=f"event-{route}-{expected_head_generation}",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=job.job_id,
        predecessor_receipt_ref=predecessor_receipt_ref,
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
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        commit = _oracle_write(store, job, initial, route="v3-relation", replacement=replacement)
    expected_ref = (
        _oracle_frontier_ref(initial.key, 2, replacement)
        if replacement is not None
        else initial.frontier_ref
    )
    assert commit.head.evaluation_frontier_before_ref == initial.frontier_ref
    assert commit.head.evaluation_frontier_ref == expected_ref == commit.frontier.frontier_ref
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
    with store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt):
        first = _oracle_write(store, job, initial, route="v3-same-route", replacement=None)
    replacement = _value("compiled-uncommitted", "selected-uncommitted")
    with (
        store.job_execution_fence(job_id=job.job_id, worker_id=worker, attempt=attempt),
        pytest.raises(ValueError, match="acquisition_action_predecessor_conflict"),
    ):
        # CAS is attempted first, then the already-present route head rejects this append.
        _oracle_write(store, job, initial, route="v3-same-route", replacement=replacement)
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


def test_v3_sql_head_insert_abort_rolls_back_frontier_and_history(tmp_path: Path) -> None:
    path = tmp_path / "v3-insert-abort.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=path)
    _, initial, _ = _bootstrap(store, tmp_path)
    job, worker, attempt = _create_action_job(store, job_id="v3-abort-action")
    replacement = _value("compiled-aborted", "selected-aborted")
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
        _oracle_write(store, job, initial, route="v3-aborted", replacement=replacement)
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
