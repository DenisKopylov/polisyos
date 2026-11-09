"""Exercise candidate experiment generation publication at the SQL boundary only; no authority."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

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


def _reuse_request_payload(
    *,
    terminal_ref: str,
    terminal_profile: str,
    route_id: str = _ACTION_SCOPE["route_id"],
) -> dict[str, object]:
    def selected_ref(digit: str, kind: str) -> dict[str, str]:
        return {
            "artifact_id": "sha256:" + digit * 64,
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + digit.upper() * 64,
        }

    return {
        "route_id": route_id,
        "predecessor_terminal_ref": {
            "artifact_id": terminal_ref,
            "kind": "runtime_quality.acquisition_route_loop_receipt",
            "media_type": "application/json",
            "manifest_profile_sha256": terminal_profile,
        },
        "predecessor_action_ref": selected_ref(
            "1", "runtime_quality.acquisition_candidate_action_receipt"
        ),
        "source_ref": selected_ref("2", "runtime.quality.candidate_acquisition_source"),
        "n5_input_ref": selected_ref("3", "runtime.quality.candidate_simulation_n5_input"),
        "n5_execution_ref": selected_ref("4", "runtime.quality.candidate_simulation_execution"),
        "n5_result_ref": selected_ref("5", "polisyos.runtime.joint_simulation_result"),
        "policy_ref": selected_ref("6", "runtime_quality.candidate_unpriced_acquisition_policy"),
        "idempotency_key": "reuse-generation-2",
        "human_decision_record_ref": None,
    }


def _prepared_reuse_publication(
    *,
    expected_previous_terminal_ref: str,
    expected_previous_terminal_manifest_profile_sha256: str,
    request_terminal_ref: str | None = None,
    request_terminal_profile: str | None = None,
    action_generation: int = 2,
    job_id: str = "generation-2-reuse-job",
    action_kind: str = "runtime.evidence.candidate_experiment.reuse",
    include_replay_pins: bool = False,
) -> _PreparedAcquisitionActionHeadPublication:
    request_payload = _reuse_request_payload(
        terminal_ref=request_terminal_ref or expected_previous_terminal_ref,
        terminal_profile=(
            request_terminal_profile or expected_previous_terminal_manifest_profile_sha256
        ),
    )
    if include_replay_pins:
        request_payload["replay_pins"] = {}
    request_json = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    receipt_ref = "sha256:" + "f" * 64
    return _PreparedAcquisitionActionHeadPublication(
        tenant_id=_ACTION_SCOPE["tenant_id"],
        cell_id=_ACTION_SCOPE["cell_id"],
        run_id=_ACTION_SCOPE["run_id"],
        source_job_id=_ACTION_SCOPE["source_job_id"],
        route_id=_ACTION_SCOPE["route_id"],
        action_generation=action_generation,
        job_id=job_id,
        action_kind=action_kind,  # type: ignore[arg-type]
        request_json=request_json,
        decision_ref="sha256:" + "1" * 64,
        payload_ref="sha256:" + "2" * 64,
        receipt_ref=receipt_ref,
        receipt_sha256=receipt_ref,
        receipt_manifest_profile_sha256="sha256:" + "3" * 64,
        durable_event_id="evt-generation-2-reuse-requested",
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


def test_sql_publication_accepts_generation_two_reuse_after_exact_terminal(tmp_path) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    publication = _prepared_reuse_publication(
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
    assert _head(store, action_generation=1) == terminal


@pytest.mark.parametrize("mismatch", ["terminal_ref", "terminal_profile"])
def test_sql_publication_rejects_reuse_when_actual_previous_terminal_differs(
    tmp_path, mismatch: str
) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    expected_ref = terminal.receipt_ref
    expected_profile = terminal.receipt_manifest_profile_sha256
    if mismatch == "terminal_ref":
        expected_ref = "sha256:" + "6" * 64
    else:
        expected_profile = "sha256:" + "7" * 64
    publication = _prepared_reuse_publication(
        expected_previous_terminal_ref=expected_ref,
        expected_previous_terminal_manifest_profile_sha256=expected_profile,
    )

    with pytest.raises(ValueError, match="acquisition_action_generation_predecessor_conflict"):
        _create_candidate_action_job(store, publication)

    assert store.get_job(publication.job_id) is None
    assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=1) == terminal


@pytest.mark.parametrize(
    "malformation",
    [
        "terminal_ref",
        "selected_id",
        "selected_profile",
        "kind",
        "media_type",
        "mixed_shape",
    ],
)
def test_sql_publication_rejects_malformed_reuse_predecessor_before_job_publication(
    tmp_path, malformation: str
) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    publication = _prepared_reuse_publication(
        expected_previous_terminal_ref=terminal.receipt_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            terminal.receipt_manifest_profile_sha256
        ),
    )
    request_payload = json.loads(publication.request_json)
    if malformation == "terminal_ref":
        request_payload["predecessor_terminal_ref"]["manifest_profile_sha256"] = None
    elif malformation == "selected_id":
        request_payload["predecessor_terminal_ref"]["artifact_id"] = "sha256:" + "8" * 64
    elif malformation == "selected_profile":
        request_payload["predecessor_terminal_ref"]["manifest_profile_sha256"] = (
            "sha256:" + "9" * 64
        )
    elif malformation == "kind":
        request_payload["predecessor_terminal_ref"]["kind"] = "runtime.quality.other_receipt"
    elif malformation == "media_type":
        request_payload["predecessor_terminal_ref"]["media_type"] = "application/octet-stream"
    else:
        request_payload["replay_pins"] = {}
    publication = replace(
        publication,
        request_json=json.dumps(request_payload, sort_keys=True, separators=(",", ":")),
    )

    with pytest.raises(ValueError, match="prepared_acquisition_action_predecessor_invalid"):
        _create_candidate_action_job(store, publication)

    assert store.get_job(publication.job_id) is None
    assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=1) == terminal


def test_sql_publication_rejects_generation_one_reuse_and_unknown_action_kind(tmp_path) -> None:
    store = _make_store(tmp_path)
    terminal = _seed_generation_one(store, terminal=True)
    generation_one = _prepared_reuse_publication(
        expected_previous_terminal_ref=terminal.receipt_ref,
        expected_previous_terminal_manifest_profile_sha256=(
            terminal.receipt_manifest_profile_sha256
        ),
        action_generation=1,
    )
    unknown_kind = replace(
        _prepared_reuse_publication(
            expected_previous_terminal_ref=terminal.receipt_ref,
            expected_previous_terminal_manifest_profile_sha256=(
                terminal.receipt_manifest_profile_sha256
            ),
            job_id="generation-2-unknown-kind",
        ),
        action_kind="runtime.evidence.unrecognized.action",  # type: ignore[arg-type]
    )

    for publication in (generation_one, unknown_kind):
        with pytest.raises(ValueError):
            _create_candidate_action_job(store, publication)
        assert store.get_job(publication.job_id) is None
        assert _head(store, action_generation=2) is None
    assert _head(store, action_generation=1) == terminal


def _reuse_enqueue_admission_inputs():
    from polisyos.runtime.quality.candidate_experiment_reuse import (
        CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_reuse import (
        _reuse_action_selection,
    )

    selection = _reuse_action_selection()
    predecessor = selection.predecessor_terminal_ref
    publication = replace(
        _prepared_reuse_publication(
            expected_previous_terminal_ref=str(predecessor.artifact_id),
            expected_previous_terminal_manifest_profile_sha256=(
                predecessor.manifest_profile_sha256
            ),
            job_id=selection.action_job_id,
        ),
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        route_id=selection.route_id,
        action_generation=selection.action_generation,
        action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
        request_json=json.dumps(
            selection.request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    payload = {
        "action_kind": CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
        "tenant_id": selection.tenant_id,
        "cell_id": selection.cell_id,
        "run_id": selection.run_id,
        "route_id": selection.route_id,
        "decision_ref": publication.decision_ref,
        "request": selection.request.model_dump(mode="json"),
        "reuse_selection": selection.model_dump(mode="json"),
    }
    return selection, publication, payload


def _reuse_enqueue_probe():
    from types import SimpleNamespace

    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
    from polisyos.runtime.http.services.control.job_diagnostics import (
        ControlJobDiagnosticsMixin,
    )

    class PersistReachedError(RuntimeError):
        pass

    class EnqueueProbe(ControlJobDiagnosticsMixin):
        def __init__(self) -> None:
            self.persist_calls = 0
            self._control_store = SimpleNamespace(get_job=lambda _job_id: None)
            self._metrics = None

        def _attach_job_actor_scope(self, payload, *, policy):
            return dict(payload)

        def _enrich_job_payload(self, payload, *, request_id):
            return dict(payload)

        def _persist_job_payload(self, *, job_kind, payload):
            self.persist_calls += 1
            raise PersistReachedError("intentional persistence boundary")

    policy = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="embedded",
        state_store_backend="sqlite",
        sqlite_path=":memory:",
        postgres_dsn=None,
    ).resolve(requested_profile=None)
    return EnqueueProbe(), policy, PersistReachedError


def test_enqueue_rejects_same_job_retry_with_tampered_reuse_ref_before_persist() -> None:
    selection, publication, payload = _reuse_enqueue_admission_inputs()
    payload["reuse_selection"]["predecessor_terminal_ref"]["manifest_profile_sha256"] = (
        "sha256:" + "0" * 64
    )
    probe, policy, _persist_reached = _reuse_enqueue_probe()

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_prepared_job_binding_mismatch",
    ):
        probe._enqueue_job(
            job_id=selection.action_job_id,
            job_kind="acquisition",
            run_id=selection.run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            prepared_acquisition_action_head=publication,
        )

    assert probe.persist_calls == 0


def test_enqueue_admits_exact_reuse_selection_to_persistence_on_same_job_retry() -> None:
    selection, publication, payload = _reuse_enqueue_admission_inputs()
    probe, policy, persist_reached = _reuse_enqueue_probe()

    with pytest.raises(persist_reached, match="intentional persistence boundary"):
        probe._enqueue_job(
            job_id=selection.action_job_id,
            job_kind="acquisition",
            run_id=selection.run_id,
            pipeline_id=None,
            payload=payload,
            policy=policy,
            prepared_acquisition_action_head=publication,
        )

    assert probe.persist_calls == 1
