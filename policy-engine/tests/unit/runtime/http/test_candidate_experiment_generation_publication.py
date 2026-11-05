"""Exercise candidate experiment generation publication at the SQL boundary only; no authority."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobRecord,
    ControlPlaneStore,
    _PreparedAcquisitionActionHeadPublication,
)

_ACTION_SCOPE = {
    "tenant_id": "tenant-a",
    "cell_id": "cell-a",
    "run_id": "run-a",
    "source_job_id": "source-job",
    "route_id": "sha256:" + "a" * 64,
}


def _make_store(tmp_path) -> ControlPlaneStore:
    return ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control-plane.sqlite3",
    )


def _head(
    store: ControlPlaneStore, *, action_generation: int
) -> AcquisitionActionHeadRecord | None:
    return store.get_acquisition_action_head(
        **_ACTION_SCOPE,
        action_generation=action_generation,
    )


def _seed_generation_one(
    store: ControlPlaneStore, *, terminal: bool
) -> AcquisitionActionHeadRecord:
    """Seed synthetic SQL-boundary phase rows through the canonical store API.

    These pointers exercise publication mechanics only; they are not verified
    receipts and carry no evidence or policy authority.
    """
    requested_ref = "sha256:" + "b" * 64
    requested_profile = "sha256:" + "c" * 64
    requested = store.advance_acquisition_action_head(
        **_ACTION_SCOPE,
        action_generation=1,
        expected_head_generation=0,
        receipt_ref=requested_ref,
        receipt_sha256=requested_ref,
        durable_event_id="evt-generation-1-requested",
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        job_id="generation-1-job",
        predecessor_receipt_ref=None,
        receipt_manifest_profile_sha256=requested_profile,
    )
    if not terminal:
        return requested

    terminal_ref = "sha256:" + "d" * 64
    return store.advance_acquisition_action_head(
        **_ACTION_SCOPE,
        action_generation=1,
        expected_head_generation=1,
        receipt_ref=terminal_ref,
        receipt_sha256=terminal_ref,
        durable_event_id="evt-generation-1-terminal",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="none",
        job_id="generation-1-job",
        predecessor_receipt_ref=requested_ref,
        receipt_manifest_profile_sha256="sha256:" + "e" * 64,
    )


def _prepared_publication(
    *,
    action_generation: int = 2,
    job_id: str = "generation-2-job",
    receipt_digit: str = "f",
    expected_previous_terminal_ref: str | None,
    expected_previous_terminal_manifest_profile_sha256: str | None,
) -> _PreparedAcquisitionActionHeadPublication:
    receipt_ref = "sha256:" + receipt_digit * 64
    request_payload: dict[str, object] = {"idempotency_key": job_id}
    if action_generation > 1:
        request_payload["replay_pins"] = {
            "predecessor_terminal_ref": {
                "artifact_id": expected_previous_terminal_ref,
                "kind": "runtime_quality.acquisition_route_loop_receipt",
                "media_type": "application/json",
                "manifest_profile_sha256": (expected_previous_terminal_manifest_profile_sha256),
            }
        }
    return _PreparedAcquisitionActionHeadPublication(
        tenant_id=_ACTION_SCOPE["tenant_id"],
        cell_id=_ACTION_SCOPE["cell_id"],
        run_id=_ACTION_SCOPE["run_id"],
        source_job_id=_ACTION_SCOPE["source_job_id"],
        route_id=_ACTION_SCOPE["route_id"],
        action_generation=action_generation,
        job_id=job_id,
        action_kind="runtime.evidence.acquisition.candidate_experiment.execute",
        request_json=json.dumps(request_payload, sort_keys=True, separators=(",", ":")),
        decision_ref="sha256:" + "1" * 64,
        payload_ref="sha256:" + "2" * 64,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        receipt_manifest_profile_sha256="sha256:" + "3" * 64,
        durable_event_id="evt-" + job_id + "-requested",
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        predecessor_receipt_ref=None,
        expected_head_generation=0,
        expected_previous_terminal_ref=expected_previous_terminal_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            expected_previous_terminal_manifest_profile_sha256
        ),
    )


def _create_candidate_action_job(
    store: ControlPlaneStore,
    publication: _PreparedAcquisitionActionHeadPublication,
) -> ControlJobRecord:
    return store.create_job(
        job_id=publication.job_id,
        kind="acquisition",
        run_id=publication.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=publication.payload_ref,
        submitted_by="test-sql-boundary-mechanics",
        prepared_acquisition_action_head=publication,
    )


def test_sql_publication_accepts_generation_two_after_terminal_generation_one(tmp_path) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    publication = _prepared_publication(
        expected_previous_terminal_ref=terminal.receipt_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            terminal.receipt_manifest_profile_sha256
        ),
    )

    created = _create_candidate_action_job(store, publication)

    second = _head(store, action_generation=2)
    assert created.job_id == publication.job_id
    assert created.state == "pending"
    assert second is not None
    assert second.action_generation == 2
    assert second.head_generation == 1
    assert second.receipt_ref == publication.receipt_ref
    assert second.predecessor_receipt_ref is None
    assert publication.expected_head_generation == 0
    assert _head(store, action_generation=1) == terminal


@pytest.mark.parametrize("mismatch", ["terminal_ref", "terminal_profile"])
def test_sql_publication_rejects_mismatched_generation_predecessor(tmp_path, mismatch: str) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    expected_ref = terminal.receipt_ref
    expected_profile = terminal.receipt_manifest_profile_sha256
    if mismatch == "terminal_ref":
        expected_ref = "sha256:" + "6" * 64
    else:
        expected_profile = "sha256:" + "7" * 64
    publication = _prepared_publication(
        expected_previous_terminal_ref=expected_ref,
        expected_previous_terminal_manifest_profile_sha256=expected_profile,
    )

    with pytest.raises(ValueError):
        _create_candidate_action_job(store, publication)

    assert store.get_job(publication.job_id) is None
    assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=1) == terminal


def test_sql_publication_rejects_pending_generation_predecessor(tmp_path) -> None:
    store = _make_store(tmp_path)
    pending = _seed_generation_one(store, terminal=False)
    publication = _prepared_publication(
        expected_previous_terminal_ref=pending.receipt_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            pending.receipt_manifest_profile_sha256
        ),
    )

    with pytest.raises(ValueError):
        _create_candidate_action_job(store, publication)

    assert store.get_job(publication.job_id) is None
    assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=1) == pending


def test_sql_publication_rejects_skipped_generation(tmp_path) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    publication = _prepared_publication(
        action_generation=3,
        job_id="generation-3-job",
        receipt_digit="8",
        expected_previous_terminal_ref=terminal.receipt_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            terminal.receipt_manifest_profile_sha256
        ),
    )

    with pytest.raises(ValueError):
        _create_candidate_action_job(store, publication)

    assert store.get_job(publication.job_id) is None
    assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=3) is None
    assert _head(store, action_generation=1) == terminal


def test_sql_publication_rejects_stale_concurrent_generation_without_partial_job(
    tmp_path,
) -> None:
    database = tmp_path / "control-plane.sqlite3"
    stores = tuple(ControlPlaneStore(backend="sqlite", sqlite_path=database) for _ in range(2))
    terminal = _seed_generation_one(stores[0], terminal=True)
    publications = (
        _prepared_publication(
            job_id="generation-2-contender-a",
            receipt_digit="9",
            expected_previous_terminal_ref=terminal.receipt_ref,
            expected_previous_terminal_manifest_profile_sha256=(
                terminal.receipt_manifest_profile_sha256
            ),
        ),
        _prepared_publication(
            job_id="generation-2-contender-b",
            receipt_digit="4",
            expected_previous_terminal_ref=terminal.receipt_ref,
            expected_previous_terminal_manifest_profile_sha256=(
                terminal.receipt_manifest_profile_sha256
            ),
        ),
    )
    barrier = threading.Barrier(2)

    def publish(index: int) -> tuple[str, str, str | None]:
        barrier.wait(timeout=10)
        try:
            _create_candidate_action_job(stores[index], publications[index])
        except ValueError as error:
            return "rejected", publications[index].job_id, str(error)
        return "published", publications[index].job_id, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(publish, range(2)))

    assert sorted(outcome[0] for outcome in outcomes) == ["published", "rejected"]
    winner = next(job_id for status, job_id, _error in outcomes if status == "published")
    loser = next(job_id for status, job_id, _error in outcomes if status == "rejected")
    winning_publication = next(
        publication for publication in publications if publication.job_id == winner
    )
    assert stores[0].get_job(winner) is not None
    assert stores[0].get_job(loser) is None
    second = _head(stores[0], action_generation=2)
    assert second is not None
    assert second.job_id == winner
    assert second.head_generation == 1
    assert second.receipt_ref == winning_publication.receipt_ref
    assert _head(stores[0], action_generation=1) == terminal
