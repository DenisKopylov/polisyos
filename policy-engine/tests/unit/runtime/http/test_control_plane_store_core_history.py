"""Exact Core attempt selection reads immutable SQLite terminal event history."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.http.services.adapters.core_run import derive_control_job_core_run_id
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlJobRecord,
    ControlPlaneStore,
)


def _create_history_job(
    store: ControlPlaneStore, *, job_id: str = "job-core-history"
) -> ControlJobRecord:
    return store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="run-" + job_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="history-fixture",
    )


@pytest.fixture
def history_store(tmp_path: Path) -> Iterator[tuple[ControlPlaneStore, ControlJobRecord]]:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        yield store, _create_history_job(store)
    finally:
        store.close()


def _core_id(job: ControlJobRecord, attempt: int) -> str:
    assert job.run_id is not None
    return derive_control_job_core_run_id(
        job_id=job.job_id, control_run_id=job.run_id, attempt=attempt
    )


def _append_terminal(
    store: ControlPlaneStore, job: ControlJobRecord, *, state: str, attempt: int
) -> dict[str, Any]:
    payload = {"state": state, "attempt": attempt, "lease_owner": f"worker-{attempt}"}
    store.append_event(job_id=job.job_id, event_type="job_" + state, payload=payload)
    return payload


def test_exact_core_terminal_history_keeps_old_failure_after_new_completion(
    history_store: tuple[ControlPlaneStore, ControlJobRecord],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh reader selects stored attempts without consulting a current row or lease."""
    store, job = history_store
    failed = _append_terminal(store, job, state="failed", attempt=1)
    completed = _append_terminal(store, job, state="completed", attempt=2)
    # The named denominator is terminal history, not every adjacent event payload.
    store.append_event(
        job_id=job.job_id, event_type="job_progress", payload={"attempt": True, "state": "invalid"}
    )
    latest = store.get_job_terminal_source_event_record(job.job_id)
    assert latest.event_type == "job_completed" and latest.payload == completed
    current = store.get_job(job.job_id)
    assert current is not None and current.state == "pending" and current.attempt == 0

    reader = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        with pytest.raises(ControlJobLeaseLostError, match="execution identity is not bound"):
            reader.current_execution_job_record()

        def refuse_current_job_lookup(*_args: Any, **_kwargs: Any) -> Any:
            pytest.fail("immutable terminal history consulted the current job head")

        monkeypatch.setattr(reader, "get_job", refuse_current_job_lookup)
        first = reader._get_job_terminal_source_event_for_core_run(
            job_id=job.job_id,
            control_run_id=str(job.run_id),
            core_run_id=_core_id(job, 1),
            expected_state="failed",
        )
        second = reader._get_job_terminal_source_event_for_core_run(
            job_id=job.job_id,
            control_run_id=str(job.run_id),
            core_run_id=_core_id(job, 2),
            expected_state="completed",
        )
        assert first.event_id < second.event_id == latest.event_id
        assert first.job_id == second.job_id == job.job_id
        assert first.event_type == "job_failed" and first.payload == failed
        assert second.event_type == "job_completed" and second.payload == completed
        for source, payload in ((first, failed), (second, completed)):
            stored_json = json.dumps(payload, sort_keys=True)
            assert source.payload_sha256 == (
                "sha256:" + hashlib.sha256(stored_json.encode("utf-8")).hexdigest()
            )
    finally:
        reader.close()


@pytest.mark.parametrize("changed", ["core", "control-run", "job", "state"])
def test_exact_core_terminal_history_refuses_wrong_selection(
    history_store: tuple[ControlPlaneStore, ControlJobRecord], changed: str
) -> None:
    store, job = history_store
    _append_terminal(store, job, state="failed", attempt=1)
    _append_terminal(store, job, state="completed", attempt=2)
    query: dict[str, Any] = {
        "job_id": job.job_id,
        "control_run_id": job.run_id,
        "core_run_id": _core_id(job, 1),
        "expected_state": "failed",
    }
    query.update(
        {
            "core": {"core_run_id": "control-" + "0" * 64},
            "control-run": {"control_run_id": "run-foreign"},
            "job": {"job_id": "job-foreign"},
            "state": {"expected_state": "completed"},
        }[changed]
    )
    with pytest.raises(
        ControlJobLeaseLostError, match="control job exact Core terminal history not established"
    ):
        store._get_job_terminal_source_event_for_core_run(**query)


@pytest.mark.parametrize("malformed_first", [False, True], ids=["later", "earlier"])
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"state": "failed", "attempt": True}, id="bool-attempt"),
        pytest.param({"state": "failed", "attempt": "2"}, id="string-attempt"),
        pytest.param({"state": "failed", "attempt": 2.0}, id="float-attempt"),
        pytest.param({"state": "failed", "attempt": None}, id="null-attempt"),
        pytest.param({"state": "failed"}, id="absent-attempt"),
        pytest.param({"state": "failed", "attempt": 0}, id="zero-attempt"),
        pytest.param({"state": "completed", "attempt": 2}, id="mismatched-state"),
        pytest.param({"attempt": 2}, id="absent-state"),
    ],
)
def test_exact_core_terminal_history_refuses_malformed_named_denominator(
    history_store: tuple[ControlPlaneStore, ControlJobRecord],
    payload: dict[str, Any],
    malformed_first: bool,
) -> None:
    """A matching valid row cannot hide another malformed terminal record."""
    store, job = history_store
    if not malformed_first:
        _append_terminal(store, job, state="failed", attempt=1)
    store.append_event(job_id=job.job_id, event_type="job_failed", payload=payload)
    if malformed_first:
        _append_terminal(store, job, state="failed", attempt=1)
    with pytest.raises(ControlJobLeaseLostError, match="control job terminal history is malformed"):
        store._get_job_terminal_source_event_for_core_run(
            job_id=job.job_id,
            control_run_id=str(job.run_id),
            core_run_id=_core_id(job, 1),
            expected_state="failed",
        )


@pytest.mark.parametrize("duplicate_state", ["failed", "completed"])
def test_exact_core_terminal_history_refuses_duplicate_attempt_events(
    history_store: tuple[ControlPlaneStore, ControlJobRecord], duplicate_state: str
) -> None:
    """Even a different terminal state cannot disambiguate one derived Core attempt."""
    store, job = history_store
    _append_terminal(store, job, state="failed", attempt=1)
    _append_terminal(store, job, state=duplicate_state, attempt=1)
    with pytest.raises(
        ControlJobLeaseLostError, match="control job exact Core terminal history not established"
    ):
        store._get_job_terminal_source_event_for_core_run(
            job_id=job.job_id,
            control_run_id=str(job.run_id),
            core_run_id=_core_id(job, 1),
            expected_state="failed",
        )


def test_exact_core_terminal_history_excludes_another_jobs_malformed_events(
    history_store: tuple[ControlPlaneStore, ControlJobRecord],
) -> None:
    store, job = history_store
    expected = _append_terminal(store, job, state="failed", attempt=1)
    foreign = _create_history_job(store, job_id="job-foreign-core-history")
    store.append_event(job_id=foreign.job_id, event_type="job_failed", payload={"attempt": True})
    selected = store._get_job_terminal_source_event_for_core_run(
        job_id=job.job_id,
        control_run_id=str(job.run_id),
        core_run_id=_core_id(job, 1),
        expected_state="failed",
    )
    assert selected.job_id == job.job_id and selected.payload == expected
